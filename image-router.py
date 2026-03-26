#!/usr/bin/env python3
"""
自动图片路由 - 当检测到图片时自动调用本地 VL 模型
可作为独立工具使用，也可被其他脚本调用
"""

import os
import sys
import argparse
import tempfile
import base64
from pathlib import Path
from datetime import datetime

# 添加 lib 目录到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from lib.router import get_router


def detect_image_input(input_str: str) -> dict:
    """
    检测输入是否包含图片
    返回: {"is_image": bool, "type": str, "path": str, "data": bytes}
    """
    result = {"is_image": False, "type": None, "path": None, "data": None}

    # 1. 检查是否是文件路径
    if os.path.exists(input_str):
        ext = Path(input_str).suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            result["is_image"] = True
            result["type"] = "file"
            result["path"] = input_str
            return result

    # 2. 检查是否是 base64 图片数据
    if input_str.startswith("data:image/"):
        try:
            # 提取 base64 数据
            header, data = input_str.split(",", 1)
            result["is_image"] = True
            result["type"] = "base64"
            result["data"] = base64.b64decode(data)
            return result
        except:
            pass

    # 3. 检查是否是纯 base64 字符串（图片数据）
    if len(input_str) > 1000 and input_str.startswith("/9j/") or input_str.startswith("iVBOR"):
        try:
            result["is_image"] = True
            result["type"] = "base64_raw"
            result["data"] = base64.b64decode(input_str)
            return result
        except:
            pass

    return result


def analyze_image(image_path: str, prompt: str = "分析这张图片的内容", max_tokens: int = 4096) -> str:
    """使用本地 VL 模型分析图片"""
    import subprocess

    # 获取 VL 模型
    router = get_router()
    vl_model = router._get_model_by_alias("vl")
    model_id = vl_model["id"]

    # 构建 prompt
    full_prompt = f'''<|im_start|>system
You are a helpful vision assistant. 分析图片时要详细、准确。
<|im_end|>
<|im_start|>user
{prompt}
<|im_end|>
<|im_start|>assistant
'''

    # 调用 mlx_vlm
    python_path = os.path.expanduser('~/.local/pipx/venvs/mlx-vlm/bin/python')

    script = f'''
import sys
sys.path.insert(0, "{SCRIPT_DIR}")
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config

model_path = "{model_id}"
model, processor = load(model_path)
config = load_config(model_path)

messages = [
    {{"role": "user", "content": [
        {{"type": "image", "image": "{image_path}"}},
        {{"type": "text", "text": "{prompt}"}}
    ]}}
]

formatted_prompt = apply_chat_template(processor, config, messages, num_images=1)
output = generate(model, processor, formatted_prompt, image=["{image_path}"], max_tokens={max_tokens}, temperature=0.1, verbose=False)
print(output if isinstance(output, str) else str(output))
'''

    try:
        result = subprocess.run(
            [python_path, '-c', script],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.stdout.strip() if result.stdout else result.stderr
    except subprocess.TimeoutExpired:
        return "错误: 图片分析超时"
    except Exception as e:
        return f"错误: {str(e)}"


def save_temp_image(data: bytes, suffix: str = ".png") -> str:
    """保存临时图片文件"""
    temp_dir = Path(tempfile.gettempdir()) / "claude-images"
    temp_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = temp_dir / f"image_{timestamp}{suffix}"

    with open(temp_path, "wb") as f:
        f.write(data)

    return str(temp_path)


def main():
    parser = argparse.ArgumentParser(description='自动图片路由 - 检测图片并调用本地 VL 模型')
    parser.add_argument('input', nargs='?', help='输入内容（图片路径或文本）')
    parser.add_argument('--prompt', '-p', default='分析这张图片的内容', help='分析提示词')
    parser.add_argument('--check', action='store_true', help='仅检测是否是图片，不分析')
    parser.add_argument('--max-tokens', type=int, default=4096, help='最大输出 token')

    args = parser.parse_args()

    if not args.input:
        # 从 stdin 读取
        print("等待输入图片路径或粘贴图片数据...")
        args.input = sys.stdin.read().strip()

    # 检测是否是图片
    detection = detect_image_input(args.input)

    if args.check:
        print(f"是否图片: {detection['is_image']}")
        print(f"类型: {detection['type']}")
        if detection['path']:
            print(f"路径: {detection['path']}")
        return

    if not detection['is_image']:
        print(f"输入不是图片: {args.input[:100]}...")
        return

    # 获取图片路径
    if detection['type'] == 'file':
        image_path = detection['path']
    else:
        # base64 数据，保存为临时文件
        image_path = save_temp_image(detection['data'])
        print(f"图片已保存到: {image_path}")

    # 分析图片
    print(f"[vl] 分析图片中...")
    result = analyze_image(image_path, args.prompt, args.max_tokens)
    print(result)


if __name__ == '__main__':
    main()