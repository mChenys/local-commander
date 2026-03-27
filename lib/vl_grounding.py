#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VL Visual Grounding Service - 视觉定位服务（多级降级策略）
通过 VL 模型识别图像中的目标元素并返回坐标

降级策略（参考 ACrab）：dump_ui (ADB精确) -> remote_vl (局域网) -> local_vl (本地MLX)

关键改进：
1. dump_ui 优先：文本元素定位更精确可靠
2. 图像预处理：压缩优化，减少 VL 推理时间
3. 坐标反向映射：处理后的坐标 → 原始坐标
4. 元素描述增强：让 VL 模型更准确定位
"""

import os
import re
import json
import base64
import time
import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

# 延迟导入，避免启动时报错
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# MLX VL 本地模型
try:
    from mlx_vlm import load, generate
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    HAS_MLX_VLM = True
except ImportError:
    HAS_MLX_VLM = False

# 图像预处理模块
try:
    from .image_preprocessor import preprocess_image, scale_bbox, scale_coordinates
    HAS_PREPROCESSOR = True
except ImportError:
    HAS_PREPROCESSOR = False


logger = logging.getLogger(__name__)


class VLGroundingService:
    """VL 视觉定位服务 - 支持多级降级（参考 ACrab 策略）"""

    DEFAULT_CONFIG = {
        "enabled": True,
        "timeout": 60,
        "max_tokens": 2048,
        "temperature": 0.1,
        # 参考 ACrab: dump_ui 优先，更精确可靠
        "fallback_strategy": "dump_ui -> remote_vl -> local_vl",
        "dump_ui": {
            "enabled": True,
            "priority": 1,
            "_comment": "ADB UI Dump 优先，文本元素定位精确"
        },
        "remote_vl": {
            "enabled": True,
            "priority": 2,
            "base_url": "http://192.168.41.31:8000/v1",
            "model": "Qwen/Qwen3-VL-8B-Instruct",
            "api_key": "EMPTY",
            "timeout": 30
        },
        "local_vl": {
            "enabled": True,
            "priority": 3,
            "model": "mlx-community/Qwen2.5-VL-7B-Instruct-bf16",
            "timeout": 180
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 VL Grounding 服务

        Args:
            config_path: 配置文件路径，默认为 config/vl_service.json
        """
        self.config = self._load_config(config_path)
        self.remote_client = None
        self.local_model = None
        self.local_processor = None  # MLX VL processor

        if not self.config.get("enabled", True):
            logger.warning("VL Grounding 服务已禁用")
            return

        self._init_services()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """加载配置文件"""
        if config_path is None:
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config" / "vl_service.json"

        if isinstance(config_path, str):
            config_path = Path(config_path)

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # 合并配置
                    merged = {**self.DEFAULT_CONFIG}
                    if "vl_grounding" in config:
                        for key, value in config["vl_grounding"].items():
                            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                                merged[key] = {**merged[key], **value}
                            else:
                                merged[key] = value
                    return merged
            except Exception as e:
                logger.warning(f"加载 VL 配置失败: {e}，使用默认配置")

        return self.DEFAULT_CONFIG

    def _init_services(self):
        """初始化所有服务"""
        # 初始化远程 VL 客户端
        remote_config = self.config.get("remote_vl", {})
        if remote_config.get("enabled", True) and HAS_OPENAI:
            try:
                self.remote_client = OpenAI(
                    api_key=remote_config.get("api_key", "EMPTY"),
                    base_url=remote_config.get("base_url")
                )
                logger.info(f"远程 VL 客户端已初始化: {remote_config.get('base_url')}")
            except Exception as e:
                logger.warning(f"初始化远程 VL 客户端失败: {e}")

        # 本地 VL 模型延迟加载（首次使用时加载）
        local_config = self.config.get("local_vl", {})
        if local_config.get("enabled", True) and HAS_MLX_VLM:
            logger.info(f"本地 VL 模型已配置: {local_config.get('model')} (延迟加载)")

    def _load_local_model(self):
        """延迟加载本地 VL 模型"""
        if self.local_model is not None:
            return True

        if not HAS_MLX_VLM:
            logger.warning("mlx-vlm 未安装，本地 VL 模型不可用")
            return False

        local_config = self.config.get("local_vl", {})
        model_name = local_config.get("model", "mlx-community/Qwen2.5-VL-7B-Instruct-bf16")

        try:
            logger.info(f"正在加载本地 VL 模型: {model_name}")
            t0 = time.time()
            # load() 返回 (model, processor) 元组
            self.local_model, self.local_processor = load(model_name)
            logger.info(f"本地 VL 模型加载完成，耗时: {time.time() - t0:.1f}s")
            return True
        except Exception as e:
            logger.error(f"加载本地 VL 模型失败: {e}")
            return False

    def _image_to_data_url(self, image_path: str) -> str:
        """将本地图片转为 data URL"""
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        ext = Path(image_path).suffix.lower().lstrip(".")
        mime_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp", "gif": "image/gif"
        }
        mime = mime_map.get(ext, "image/png")
        return f"data:{mime};base64,{b64}"

    def _parse_json_output(self, text: str) -> Optional[Union[Dict, List]]:
        """解析模型返回的 JSON 字符串，具备强容错能力"""
        if not text:
            return None

        # 移除思考过程
        text = re.sub(r"<think.*?</think >", "", text, flags=re.DOTALL)
        text = re.sub(r"bole.*?artg", "", text, flags=re.DOTALL)

        # 移除 ```json ... ``` 包裹
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)

        # 修复尾部逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)

        # 单引号转双引号（兜底）
        if '"' not in text and "'" in text:
            text = text.replace("'", '"')

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.debug(f"原始输出片段: {text[:200]}...")
            return None

    def _normalize_bbox(self, bbox: List[float], img_width: int, img_height: int) -> List[int]:
        """将模型输出的 0-1000 归一化坐标转换为原图像素坐标"""
        if len(bbox) not in [2, 4]:
            raise ValueError(f"bbox 长度应为 2 或 4, 实际: {len(bbox)}")

        result = []
        for i, val in enumerate(bbox):
            if i % 2 == 0:
                result.append(int(val / 1000.0 * img_width))
            else:
                result.append(int(val / 1000.0 * img_height))

        result[0] = max(0, min(result[0], img_width))
        result[1] = max(0, min(result[1], img_height))
        if len(result) == 4:
            result[2] = max(0, min(result[2], img_width))
            result[3] = max(0, min(result[3], img_height))

        return result

    def _enhance_element_description(self, desc: str) -> str:
        """
        增强元素描述（参考 ACrab 的描述要求）
        让 VL 模型更准确定位
        """
        # 常见 UI 元素的描述模板
        templates = {
            # 语言相关的常见元素
            "language": "包含 '{text}' 文字的列表项，通常为语言选项，位于语言设置列表中",
            "button": "显示 '{text}' 文字的按钮，可点击",
            "menu": "显示 '{text}' 文字的菜单项",
            "input": "包含 '{text}' 占位符文字的输入框",
            "icon": "图标按钮，功能为 '{text}'",
            "text": "显示 '{text}' 文字的文本区域",
            "list_item": "包含 '{text}' 文字的列表项",
            "settings": "设置选项：'{text}'",
        }

        desc_lower = desc.lower()

        # 检测元素类型
        element_type = "text"  # 默认
        text_content = desc

        if "language" in desc_lower or "语言" in desc or any(lang in desc_lower for lang in ["english", "chinese", "中文", "english", "日本語", "deutsch"]):
            element_type = "language"
            # 提取语言名称
            for lang in ["English", "Chinese", "中文", "English", "日本語", "Deutsch", "Français", "Español"]:
                if lang.lower() in desc_lower:
                    text_content = lang
                    break
        elif "button" in desc_lower or "按钮" in desc:
            element_type = "button"
        elif "menu" in desc_lower or "菜单" in desc:
            element_type = "menu"
        elif "input" in desc_lower or "输入" in desc or "框" in desc:
            element_type = "input"
        elif "icon" in desc_lower or "图标" in desc:
            element_type = "icon"
        elif "setting" in desc_lower or "设置" in desc:
            element_type = "settings"
        elif "list" in desc_lower or "列表" in desc:
            element_type = "list_item"

        # 应用模板
        if element_type in templates:
            return templates[element_type].format(text=text_content)

        # 默认增强
        return f"查找包含 '{desc}' 文字的 UI 元素"

    def _save_debug_image(self, image_path: str, elements: List[Dict], output_path: str) -> str:
        """
        在截图上绘制 bbox 和标签，用于调试验证（参考 ACrab）
        """
        if not HAS_PIL:
            return ""

        try:
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            draw = ImageDraw.Draw(img)

            # 颜色列表
            colors = ["red", "blue", "green", "orange", "purple", "cyan"]

            for i, elem in enumerate(elements):
                bbox = elem.get("bbox", [])
                label = elem.get("label", "unknown")
                confidence = elem.get("confidence", 1.0)
                color = colors[i % len(colors)]

                if len(bbox) == 4:
                    # 绘制矩形
                    draw.rectangle(bbox, outline=color, width=3)

                    # 绘制标签背景
                    label_text = f"{label} ({confidence:.2f})"
                    try:
                        # 尝试使用默认字体
                        text_bbox = draw.textbbox((bbox[0], bbox[1] - 20), label_text)
                        draw.rectangle([text_bbox[0] - 2, text_bbox[1] - 2, text_bbox[2] + 2, text_bbox[3] + 2], fill=color)
                        draw.text((bbox[0], bbox[1] - 20), label_text, fill="white")
                    except Exception:
                        # 如果字体失败，只画矩形
                        pass

            img.save(output_path)
            logger.info(f"调试图像保存: {output_path}")
            return output_path

        except Exception as e:
            logger.warning(f"保存调试图像失败: {e}")
            return ""

    def _detect_remote_vl(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """使用远程 VL 服务检测元素（带图像预处理）"""
        if not self.remote_client:
            return {"success": False, "error": "远程 VL 客户端未初始化", "method": "remote_vl"}

        remote_config = self.config.get("remote_vl", {})

        try:
            # 1. 图像预处理
            scale_factor = 1.0
            processed_path = image_path
            original_width, original_height = None, None

            if HAS_PREPROCESSOR:
                preprocessed = preprocess_image(image_path)
                if preprocessed.get("success"):
                    processed_path = preprocessed["processed"]["path"]
                    scale_factor = preprocessed.get("scale_factor", 1.0)
                    original_width = preprocessed["original"].get("width")
                    original_height = preprocessed["original"].get("height")
                    logger.info(f"[remote_vl] 图像预处理: scale_factor={scale_factor:.2f}")
            elif HAS_PIL:
                with Image.open(image_path) as img:
                    original_width, original_height = img.size

            # 2. 增强 prompt
            enhanced_prompt_text = self._enhance_element_description(prompt)
            enhanced_prompt = f"""{enhanced_prompt_text}

【输出要求】
1. 仅输出标准 JSON，不要包含 Markdown 或其他解释
2. bbox 坐标使用 0~1000 归一化格式 [x1, y1, x2, y2]，其中 (0,0) 为左上角，(1000,1000) 为右下角
3. 示例格式：
{{
  "results": [
    {{"label": "目标名称", "bbox_2d": [120, 340, 280, 420], "confidence": 0.96}}
  ]
}}
"""

            data_url = self._image_to_data_url(processed_path)

            messages = [
                {"role": "system", "content": [{"type": "text", "text": "You are a helpful visual grounding assistant."}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": enhanced_prompt}
                    ]
                }
            ]

            logger.info(f"[remote_vl] 调用: {remote_config.get('model')} @ {remote_config.get('base_url')}")
            t0 = time.time()

            completion = self.remote_client.chat.completions.create(
                model=remote_config.get("model"),
                messages=messages,
                temperature=self.config.get("temperature", 0.1),
                max_tokens=self.config.get("max_tokens", 2048),
                timeout=remote_config.get("timeout", 30)
            )

            inference_time = time.time() - t0
            response_text = completion.choices[0].message.content
            logger.info(f"[remote_vl] 成功，耗时: {inference_time:.2f}s")

            result = self._parse_vl_response(response_text, original_width, original_height, "remote_vl", inference_time)

            # 3. 坐标反向映射（处理后的坐标 → 原始坐标）
            if result.get("success") and scale_factor != 1.0:
                for elem in result.get("elements", []):
                    if "bbox" in elem:
                        elem["bbox"] = scale_bbox(elem["bbox"], scale_factor, direction="up")
                    if "center" in elem:
                        elem["center"] = list(scale_coordinates(tuple(elem["center"]), scale_factor, direction="up"))

            return result

        except Exception as e:
            logger.warning(f"[remote_vl] 失败: {e}")
            return {"success": False, "error": str(e), "method": "remote_vl"}

    def _detect_local_vl(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """使用本地 MLX VL 模型检测元素"""
        if not self._load_local_model():
            return {"success": False, "error": "本地 VL 模型加载失败", "method": "local_vl"}

        local_config = self.config.get("local_vl", {})

        try:
            # 获取图像尺寸
            img_width, img_height = None, None
            if HAS_PIL:
                with Image.open(image_path) as img:
                    img_width, img_height = img.size

            enhanced_prompt = f"""{prompt}

【输出要求】
1. 仅输出标准 JSON，不要包含 Markdown 或其他解释
2. bbox 坐标使用 0~1000 归一化格式 [x1, y1, x2, y2]
3. 示例：{{"results": [{{"label": "目标", "bbox_2d": [100, 200, 300, 400], "confidence": 0.95}}]}}
"""

            logger.info(f"[local_vl] 调用: {local_config.get('model')}")
            t0 = time.time()

            # 关键：使用 apply_chat_template 格式化 prompt（包含图片占位符）
            try:
                from mlx_vlm.prompt_utils import apply_chat_template
                formatted_prompt = apply_chat_template(
                    self.local_processor,
                    self.local_model.config,
                    enhanced_prompt,
                    num_images=1,  # 必须指定图片数量，添加 <|vision_start|><|image_pad|><|vision_end|>
                )
            except Exception as e:
                logger.warning(f"[local_vl] apply_chat_template 失败，使用原始 prompt: {e}")
                formatted_prompt = enhanced_prompt

            # 使用 MLX VL 生成
            output = generate(
                self.local_model,
                self.local_processor,
                formatted_prompt,
                image_path,
                verbose=False,
                max_tokens=self.config.get("max_tokens", 2048),
                temperature=self.config.get("temperature", 0.1)
            )

            inference_time = time.time() - t0
            # generate 返回 GenerationResult 对象
            if hasattr(output, 'text'):
                response_text = output.text
            else:
                response_text = str(output)
            logger.info(f"[local_vl] 成功，耗时: {inference_time:.2f}s")

            return self._parse_vl_response(response_text, img_width, img_height, "local_vl", inference_time)

        except Exception as e:
            logger.warning(f"[local_vl] 失败: {e}")
            return {"success": False, "error": str(e), "method": "local_vl"}

    def _detect_dump_ui(self, prompt: str, image_path: str = None) -> Dict[str, Any]:
        """
        使用 ADB dump UI 检测元素（增强版，参考 ACrab）
        优先级最高，文本元素定位更精确
        """
        try:
            # 执行 UI dump
            result = subprocess.run(
                ["adb", "shell", "uiautomator", "dump", "/sdcard/ui.xml"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return {"success": False, "error": f"UI dump 失败: {result.stderr}", "method": "dump_ui"}

            # 拉取 XML
            result = subprocess.run(
                ["adb", "pull", "/sdcard/ui.xml", "/tmp/ui_dump.xml"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return {"success": False, "error": f"拉取 UI XML 失败: {result.stderr}", "method": "dump_ui"}

            # 解析 XML
            tree = ET.parse("/tmp/ui_dump.xml")
            root = tree.getroot()

            # 增强 prompt 匹配
            prompt_lower = prompt.lower().strip()
            elements = []

            # 提取关键词
            keywords = self._extract_keywords(prompt)

            for node in root.iter():
                text = node.attrib.get("text", "")
                content_desc = node.attrib.get("content-desc", "")
                resource_id = node.attrib.get("resource-id", "")
                bounds_str = node.attrib.get("bounds", "")
                clickable = node.attrib.get("clickable", "") == "true"

                # 跳过空元素
                if not text and not content_desc and not resource_id:
                    continue

                # 多策略匹配
                match_score = 0
                match_type = None
                matched_text = ""

                # 策略 1: 精确文本匹配（最高优先级）
                for kw in keywords:
                    if text and kw.lower() == text.lower():
                        match_score = 100
                        match_type = "exact_text"
                        matched_text = text
                        break

                # 策略 2: 包含匹配
                if match_score == 0:
                    for kw in keywords:
                        if text and kw.lower() in text.lower():
                            match_score = 80
                            match_type = "contains_text"
                            matched_text = text
                            break

                # 策略 3: 反向包含匹配
                if match_score == 0:
                    for kw in keywords:
                        if text and text.lower() in kw.lower():
                            match_score = 60
                            match_type = "reverse_contains_text"
                            matched_text = text
                            break

                # 策略 4: content-desc 匹配
                if match_score == 0 and content_desc:
                    for kw in keywords:
                        if kw.lower() in content_desc.lower() or content_desc.lower() in kw.lower():
                            match_score = 70
                            match_type = "content_desc"
                            matched_text = content_desc
                            break

                # 策略 5: resource-id 匹配
                if match_score == 0 and resource_id:
                    for kw in keywords:
                        if kw.lower() in resource_id.lower():
                            match_score = 50
                            match_type = "resource_id"
                            matched_text = resource_id
                            break

                # 找到匹配
                if match_score > 0:
                    bounds = self._parse_bounds(bounds_str)
                    if bounds:
                        # 可点击元素加分
                        if clickable:
                            match_score += 10

                        elements.append({
                            "label": matched_text,
                            "bbox": bounds,
                            "center": [(bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2],
                            "confidence": min(match_score / 100.0, 1.0),
                            "match_type": match_type,
                            "match_score": match_score,
                            "clickable": clickable,
                            "resource_id": resource_id
                        })

            # 按匹配分数排序
            elements.sort(key=lambda x: x.get("match_score", 0), reverse=True)

            logger.info(f"[dump_ui] 找到 {len(elements)} 个匹配元素")

            if elements:
                return {
                    "success": True,
                    "elements": elements[:5],  # 返回前 5 个最佳匹配
                    "method": "dump_ui",
                    "inference_time": 0.1
                }
            else:
                return {"success": False, "error": "未找到匹配元素", "method": "dump_ui"}

        except Exception as e:
            logger.warning(f"[dump_ui] 失败: {e}")
            return {"success": False, "error": str(e), "method": "dump_ui"}

    def _extract_keywords(self, prompt: str) -> List[str]:
        """从 prompt 中提取关键词"""
        # 移除常见修饰词
        stop_words = ["the", "a", "an", "button", "menu", "item", "click", "tap", "find", "locate"]
        words = prompt.split()

        keywords = []
        for word in words:
            word = word.strip(".,!?").strip()
            if word.lower() not in stop_words and len(word) > 0:
                keywords.append(word)

        # 如果提取不到关键词，返回原始 prompt
        return keywords if keywords else [prompt]

    def _parse_bounds(self, bounds_str: str) -> Optional[List[int]]:
        """解析 bounds 字符串 [x1,y1][x2,y2]"""
        if not bounds_str:
            return None
        try:
            match = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
            if len(match) == 2:
                return [int(match[0][0]), int(match[0][1]), int(match[1][0]), int(match[1][1])]
        except Exception:
            pass
        return None

    def _parse_vl_response(self, response_text: str, img_width: int, img_height: int,
                           method: str, inference_time: float) -> Dict[str, Any]:
        """解析 VL 模型响应"""
        data = self._parse_json_output(response_text)
        if data is None:
            return {"success": False, "error": "无法解析模型输出", "raw_response": response_text, "method": method}

        # 提取结果
        items = []
        if isinstance(data, dict):
            for key in ["results", "items", "objects", "bounding_boxes"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items:
                items = [data]
        elif isinstance(data, list):
            items = data

        # 转换坐标
        elements = []
        for item in items:
            if not isinstance(item, dict):
                continue

            bbox = item.get("bbox_2d") or item.get("bbox") or item.get("box") or item.get("coordinates")
            if not bbox or not isinstance(bbox, (list, tuple)):
                continue

            label = item.get("label") or item.get("description") or item.get("name") or "unknown"
            confidence = item.get("confidence", 1.0)

            try:
                if img_width and img_height:
                    coords = self._normalize_bbox(bbox, img_width, img_height)
                else:
                    coords = list(bbox)

                element = {
                    "label": label,
                    "bbox": coords,
                    "confidence": confidence
                }

                if len(coords) == 4:
                    element["center"] = [(coords[0] + coords[2]) // 2, (coords[1] + coords[3]) // 2]
                elif len(coords) == 2:
                    element["center"] = coords

                elements.append(element)

            except Exception as e:
                logger.warning(f"跳过无效 bbox: {e}")
                continue

        return {
            "success": True,
            "elements": elements,
            "image_size": [img_width, img_height] if img_width else None,
            "method": method,
            "inference_time": inference_time
        }

    def detect_element(
        self,
        image_path: str,
        prompt: str,
        prefer_method: Optional[str] = None,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        检测图像中的目标元素（自动降级，参考 ACrab 策略）

        降级顺序：dump_ui (优先，精确) -> remote_vl -> local_vl

        Args:
            image_path: 图像文件路径
            prompt: 自然语言描述，如 "登录按钮" 或 "English"
            prefer_method: 优先使用的方法 (dump_ui/remote_vl/local_vl)
            debug: 是否保存调试图像

        Returns:
            {
                "success": True,
                "elements": [...],
                "method": "dump_ui",
                "fallback_chain": ["dump_ui"]
            }
        """
        if not self.config.get("enabled", True):
            return {"success": False, "error": "VL 服务已禁用"}

        if not Path(image_path).exists():
            return {"success": False, "error": f"图像文件不存在: {image_path}"}

        fallback_chain = []

        # 参考 ACrab: dump_ui 优先（文本元素定位更精确）
        dump_config = self.config.get("dump_ui", {})
        if dump_config.get("enabled", True) and (prefer_method is None or prefer_method == "dump_ui"):
            result = self._detect_dump_ui(prompt, image_path)
            fallback_chain.append("dump_ui")
            if result.get("success") and result.get("elements"):
                result["fallback_chain"] = fallback_chain
                if debug:
                    debug_path = str(Path(image_path).parent / "debug_dump_ui.jpg")
                    self._save_debug_image(image_path, result["elements"], debug_path)
                return result
            logger.info(f"[降级] dump_ui 失败，尝试下一级")

        # 2. 降级到远程 VL
        remote_config = self.config.get("remote_vl", {})
        if remote_config.get("enabled", True) and (prefer_method is None or prefer_method == "remote_vl"):
            result = self._detect_remote_vl(image_path, prompt)
            fallback_chain.append("remote_vl")
            if result.get("success") and result.get("elements"):
                result["fallback_chain"] = fallback_chain
                if debug:
                    debug_path = str(Path(image_path).parent / "debug_remote_vl.jpg")
                    self._save_debug_image(image_path, result["elements"], debug_path)
                return result
            logger.info(f"[降级] remote_vl 失败，尝试下一级")

        # 3. 降级到本地 VL
        local_config = self.config.get("local_vl", {})
        if local_config.get("enabled", True) and (prefer_method is None or prefer_method == "local_vl"):
            result = self._detect_local_vl(image_path, prompt)
            fallback_chain.append("local_vl")
            if result.get("success") and result.get("elements"):
                result["fallback_chain"] = fallback_chain
                if debug:
                    debug_path = str(Path(image_path).parent / "debug_local_vl.jpg")
                    self._save_debug_image(image_path, result["elements"], debug_path)
                return result

        return {
            "success": False,
            "error": "所有检测方法均失败",
            "fallback_chain": fallback_chain
        }

    def smart_locate(self, image_path: str, element_desc: str, prefer_dump_ui: bool = True, debug: bool = False) -> Dict[str, Any]:
        """
        智能定位策略（参考 ACrab）

        1. 优先使用 dump_ui（精确可靠）
        2. dump_ui 失败时使用 VL 视觉定位

        Args:
            image_path: 截图路径
            element_desc: 元素描述
            prefer_dump_ui: 是否优先使用 dump_ui
            debug: 是否保存调试图像
        """
        if prefer_dump_ui:
            # 尝试 dump_ui
            result = self._detect_dump_ui(element_desc, image_path)
            if result["success"]:
                if debug:
                    debug_path = str(Path(image_path).parent / "debug_smart_locate.jpg")
                    self._save_debug_image(image_path, result["elements"], debug_path)
                return result

        # 降级到 VL
        return self.detect_element(image_path, element_desc, debug=debug)

    def get_click_coords(
        self,
        image_path: str,
        element_desc: str,
        prefer_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取可点击元素的坐标（便捷方法）

        Args:
            image_path: 图像文件路径
            element_desc: 元素描述，如 "蓝色的登录按钮"
            prefer_method: 优先使用的方法

        Returns:
            {
                "success": True,
                "x": 540,
                "y": 1200,
                "label": "登录按钮",
                "confidence": 0.95,
                "method": "remote_vl"
            }
        """
        result = self.detect_element(image_path, element_desc, prefer_method)

        if not result.get("success"):
            return result

        elements = result.get("elements", [])
        if not elements:
            return {"success": False, "error": "未找到目标元素"}

        elem = elements[0]
        center = elem.get("center")

        if center:
            return {
                "success": True,
                "x": center[0],
                "y": center[1],
                "label": elem.get("label"),
                "confidence": elem.get("confidence", 1.0),
                "bbox": elem.get("bbox"),
                "method": result.get("method"),
                "fallback_chain": result.get("fallback_chain")
            }

        return {"success": False, "error": "无法计算元素中心坐标"}

    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        status = {
            "enabled": self.config.get("enabled", True),
            "fallback_strategy": self.config.get("fallback_strategy", "remote_vl -> local_vl -> dump_ui"),
            "services": {}
        }

        # 远程 VL 状态
        remote_config = self.config.get("remote_vl", {})
        status["services"]["remote_vl"] = {
            "enabled": remote_config.get("enabled", True),
            "available": self.remote_client is not None,
            "base_url": remote_config.get("base_url"),
            "model": remote_config.get("model")
        }

        # 本地 VL 状态
        local_config = self.config.get("local_vl", {})
        status["services"]["local_vl"] = {
            "enabled": local_config.get("enabled", True),
            "available": HAS_MLX_VLM,
            "model_loaded": self.local_model is not None,
            "model": local_config.get("model")
        }

        # Dump UI 状态
        status["services"]["dump_ui"] = {
            "enabled": self.config.get("dump_ui", {}).get("enabled", True),
            "available": True  # ADB 总是可用
        }

        return status


# 模块级单例
_service_instance: Optional[VLGroundingService] = None


def get_vl_grounding_service(config_path: Optional[str] = None) -> VLGroundingService:
    """获取 VL Grounding 服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = VLGroundingService(config_path)
    return _service_instance


def detect_ui_element(image_path: str, element_desc: str, prefer_method: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：检测 UI 元素并返回点击坐标"""
    service = get_vl_grounding_service()
    return service.get_click_coords(image_path, element_desc, prefer_method)
