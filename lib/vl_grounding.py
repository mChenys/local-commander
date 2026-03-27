#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VL Visual Grounding Service - 视觉定位服务
通过 VL 模型识别图像中的目标元素并返回坐标

⚠️ 重要：此服务依赖公司内部 vLLM 服务，请修改 config/vl_service.json 中的配置
"""

import os
import re
import json
import base64
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

# 延迟导入，避免启动时报错
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


logger = logging.getLogger(__name__)


class VLGroundingService:
    """VL 视觉定位服务"""

    DEFAULT_CONFIG = {
        "enabled": True,
        "base_url": "http://192.168.41.31:8000/v1",
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "api_key": "EMPTY",
        "timeout": 60,
        "max_tokens": 2048,
        "temperature": 0.1
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 VL Grounding 服务

        Args:
            config_path: 配置文件路径，默认为 config/vl_service.json
        """
        self.config = self._load_config(config_path)
        self.client = None

        if not HAS_OPENAI:
            logger.warning("openai 包未安装，VL Grounding 服务不可用")
            return

        if self.config.get("enabled", True):
            self._init_client()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """加载配置文件"""
        if config_path is None:
            # 默认配置路径
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config" / "vl_service.json"

        if isinstance(config_path, str):
            config_path = Path(config_path)

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return {**self.DEFAULT_CONFIG, **config.get("vl_grounding", {})}
            except Exception as e:
                logger.warning(f"加载 VL 配置失败: {e}，使用默认配置")

        return self.DEFAULT_CONFIG

    def _init_client(self):
        """初始化 OpenAI 客户端"""
        try:
            self.client = OpenAI(
                api_key=self.config.get("api_key", "EMPTY"),
                base_url=self.config.get("base_url")
            )
            logger.info(f"VL Grounding 客户端已初始化: {self.config.get('base_url')}")
        except Exception as e:
            logger.error(f"初始化 VL 客户端失败: {e}")
            self.client = None

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

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self.client is not None and HAS_OPENAI

    def detect_element(
        self,
        image_path: str,
        prompt: str,
        return_center: bool = True
    ) -> Dict[str, Any]:
        """
        检测图像中的目标元素

        Args:
            image_path: 图像文件路径
            prompt: 自然语言描述，如 "登录按钮"
            return_center: 是否返回中心点坐标（而非边界框）

        Returns:
            {
                "success": True,
                "elements": [
                    {
                        "label": "登录按钮",
                        "bbox": [x1, y1, x2, y2],
                        "center": [cx, cy],
                        "confidence": 0.95
                    }
                ],
                "image_size": [width, height]
            }
        """
        if not self.is_available():
            return {"success": False, "error": "VL 服务不可用，请检查配置或安装 openai 包"}

        if not Path(image_path).exists():
            return {"success": False, "error": f"图像文件不存在: {image_path}"}

        try:
            # 获取图像尺寸
            img_width, img_height = None, None
            if HAS_PIL:
                with Image.open(image_path) as img:
                    img_width, img_height = img.size

            # 准备请求
            data_url = self._image_to_data_url(image_path)

            enhanced_prompt = f"""{prompt}

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

            # 调用 VL 服务
            logger.info(f"调用 VL 模型: {self.config.get('model')} @ {self.config.get('base_url')}")
            t0 = time.time()

            completion = self.client.chat.completions.create(
                model=self.config.get("model"),
                messages=messages,
                temperature=self.config.get("temperature", 0.1),
                max_tokens=self.config.get("max_tokens", 2048),
                timeout=self.config.get("timeout", 60)
            )

            inference_time = time.time() - t0
            response_text = completion.choices[0].message.content
            logger.info(f"VL 推理完成，耗时: {inference_time:.2f}s")

            # 解析响应
            data = self._parse_json_output(response_text)
            if data is None:
                return {"success": False, "error": "无法解析模型输出", "raw_response": response_text}

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
                    # 如果有图像尺寸，转换为像素坐标
                    if img_width and img_height:
                        coords = self._normalize_bbox(bbox, img_width, img_height)
                    else:
                        coords = list(bbox)

                    element = {
                        "label": label,
                        "bbox": coords,
                        "confidence": confidence
                    }

                    # 计算中心点
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
                "inference_time": inference_time
            }

        except Exception as e:
            logger.error(f"VL 检测失败: {e}")
            return {"success": False, "error": str(e)}

    def get_click_coords(
        self,
        image_path: str,
        element_desc: str
    ) -> Dict[str, Any]:
        """
        获取可点击元素的坐标（便捷方法）

        Args:
            image_path: 图像文件路径
            element_desc: 元素描述，如 "蓝色的登录按钮"

        Returns:
            {
                "success": True,
                "x": 540,
                "y": 1200,
                "label": "登录按钮",
                "confidence": 0.95
            }
        """
        result = self.detect_element(image_path, element_desc)

        if not result.get("success"):
            return result

        elements = result.get("elements", [])
        if not elements:
            return {"success": False, "error": "未找到目标元素"}

        # 返回第一个匹配的元素
        elem = elements[0]
        center = elem.get("center")

        if center:
            return {
                "success": True,
                "x": center[0],
                "y": center[1],
                "label": elem.get("label"),
                "confidence": elem.get("confidence", 1.0),
                "bbox": elem.get("bbox")
            }

        return {"success": False, "error": "无法计算元素中心坐标"}


# 模块级单例
_service_instance: Optional[VLGroundingService] = None


def get_vl_grounding_service(config_path: Optional[str] = None) -> VLGroundingService:
    """获取 VL Grounding 服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = VLGroundingService(config_path)
    return _service_instance


def detect_ui_element(image_path: str, element_desc: str) -> Dict[str, Any]:
    """便捷函数：检测 UI 元素并返回点击坐标"""
    service = get_vl_grounding_service()
    return service.get_click_coords(image_path, element_desc)
