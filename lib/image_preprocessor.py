#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Preprocessor - 图像预处理模块
参考 ACrab 的 preprocess_image.py 设计

功能:
1. 图像压缩：限制最大尺寸，减少 VL 模型推理时间
2. 格式转换：PNG → JPG，RGBA → RGB
3. 记录缩放因子：用于坐标反向映射
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)

# 默认配置
MAX_DIMENSION = 1200  # 最大边长
JPG_QUALITY = 95      # JPG 质量


def preprocess_image(
    image_path: str,
    output_dir: Optional[str] = None,
    max_dimension: int = MAX_DIMENSION,
    quality: int = JPG_QUALITY
) -> Dict[str, Any]:
    """
    图像预处理：压缩、格式转换、返回缩放因子

    Args:
        image_path: 原始图像路径
        output_dir: 输出目录，默认与原图同目录
        max_dimension: 最大边长（像素）
        quality: JPG 质量 (1-100)

    Returns:
        {
            "original": {"width": 1080, "height": 1920, "path": "..."},
            "processed": {"width": 675, "height": 1200, "path": "..."},
            "scale_factor": 1.6,  # 原始/处理后，用于坐标反向映射
            "compressed": True,
            "format_converted": True
        }
    """
    if not HAS_PIL:
        logger.warning("PIL 未安装，跳过图像预处理")
        return _fallback_result(image_path)

    if not os.path.exists(image_path):
        logger.error(f"图像文件不存在: {image_path}")
        return {"success": False, "error": f"图像文件不存在: {image_path}"}

    try:
        # 打开原图
        img = Image.open(image_path)
        original_width, original_height = img.size
        original_format = img.format or Path(image_path).suffix.lstrip('.').upper()

        # 判断是否需要处理
        needs_resize = max(original_width, original_height) > max_dimension
        needs_format_convert = img.mode == 'RGBA' or original_format == 'PNG'

        # 如果不需要任何处理，直接返回原图信息
        if not needs_resize and not needs_format_convert:
            return {
                "success": True,
                "original": {
                    "width": original_width,
                    "height": original_height,
                    "path": image_path
                },
                "processed": {
                    "width": original_width,
                    "height": original_height,
                    "path": image_path
                },
                "scale_factor": 1.0,
                "compressed": False,
                "format_converted": False
            }

        # 计算缩放后尺寸
        if needs_resize:
            if original_width > original_height:
                new_width = max_dimension
                new_height = int(original_height * (max_dimension / original_width))
            else:
                new_height = max_dimension
                new_width = int(original_width * (max_dimension / original_height))
        else:
            new_width, new_height = original_width, original_height

        # 缩放图像
        if needs_resize:
            img = img.resize((new_width, new_height), Image.LANCZOS)

        # RGBA → RGB 转换（保存为 JPG 时必需）
        format_converted = False
        if img.mode == 'RGBA':
            # 创建白色背景
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # 使用 alpha 通道作为 mask
            img = background
            format_converted = True
        elif img.mode != 'RGB':
            img = img.convert('RGB')
            format_converted = True

        # 确定输出路径
        if output_dir is None:
            output_dir = os.path.dirname(image_path) or '/tmp'

        # 使用 JPG 格式（压缩效果更好）
        base_name = Path(image_path).stem
        processed_path = os.path.join(output_dir, f"{base_name}_processed.jpg")

        # 保存处理后的图像
        img.save(processed_path, 'JPEG', quality=quality, optimize=True)

        scale_factor = original_width / new_width if new_width > 0 else 1.0

        logger.info(f"图像预处理完成: {original_width}x{original_height} -> {new_width}x{new_height}, scale_factor={scale_factor:.2f}")

        return {
            "success": True,
            "original": {
                "width": original_width,
                "height": original_height,
                "path": image_path
            },
            "processed": {
                "width": new_width,
                "height": new_height,
                "path": processed_path
            },
            "scale_factor": scale_factor,
            "compressed": needs_resize,
            "format_converted": format_converted or original_format != 'JPEG'
        }

    except Exception as e:
        logger.error(f"图像预处理失败: {e}")
        return {"success": False, "error": str(e)}


def _fallback_result(image_path: str) -> Dict[str, Any]:
    """PIL 未安装时的回退方案"""
    return {
        "success": True,
        "original": {"path": image_path},
        "processed": {"path": image_path},
        "scale_factor": 1.0,
        "compressed": False,
        "format_converted": False,
        "warning": "PIL 未安装，跳过预处理"
    }


def scale_coordinates(
    coords: Tuple[int, int],
    scale_factor: float,
    direction: str = "up"
) -> Tuple[int, int]:
    """
    坐标缩放转换

    Args:
        coords: (x, y) 坐标
        scale_factor: 缩放因子
        direction: "up" 放大到原图，"down" 缩小到处理后图像

    Returns:
        缩放后的 (x, y) 坐标
    """
    x, y = coords
    if direction == "up":
        return (int(x * scale_factor), int(y * scale_factor))
    else:
        return (int(x / scale_factor), int(y / scale_factor))


def scale_bbox(
    bbox: list,
    scale_factor: float,
    direction: str = "up"
) -> list:
    """
    BBox 坐标缩放转换

    Args:
        bbox: [x1, y1, x2, y2] 坐标
        scale_factor: 缩放因子
        direction: "up" 放大到原图，"down" 缩小到处理后图像

    Returns:
        缩放后的 bbox
    """
    if direction == "up":
        return [int(c * scale_factor) for c in bbox]
    else:
        return [int(c / scale_factor) for c in bbox]


def get_image_size(image_path: str) -> Tuple[Optional[int], Optional[int]]:
    """获取图像尺寸"""
    if not HAS_PIL:
        return None, None

    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        return None, None


# CLI 入口
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("用法: python image_preprocessor.py <image_path>")
        sys.exit(1)

    result = preprocess_image(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
