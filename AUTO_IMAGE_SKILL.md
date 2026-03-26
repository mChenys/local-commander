---
name: auto-image
description: >
  自动图片路由 - 当检测到用户粘贴图片时，自动调用本地 VL 模型分析。

  无需手动激活，当用户粘贴图片（Ctrl+V）时自动触发。

  支持格式: PNG, JPG, JPEG, GIF, WebP, BMP
---

# 自动图片路由

## 触发规则

**当检测到以下情况时，自动调用本地 VL 模型：**

1. 用户粘贴了图片（Ctrl+V 或拖拽）
2. 用户提供了图片文件路径
3. 用户消息中包含图片相关关键词

## 执行命令

```bash
python3 ~/.claude/skills/local-commander/local-commander.py --image "<图片路径>" "分析这张图片的内容"
```

## 检测图片路径模式

- `/Users/.../*.png`
- `/Users/.../*.jpg`
- `/Users/.../*.jpeg`
- `~/Downloads/*.png`
- `~/Desktop/*.png`
- `/tmp/*.png`

## 工作流程

```
用户粘贴图片 → 检测图片路径 → 调用本地 VL 模型 → 返回分析结果 → 继续对话
```

## 示例

**用户粘贴截图后，模型应该：**

1. 检测到图片路径（如 `/Users/xxx/Downloads/screenshot.png`）
2. 执行：
   ```bash
   python3 ~/.claude/skills/local-commander/local-commander.py --image "/Users/xxx/Downloads/screenshot.png" "分析这张图片"
   ```
3. 将分析结果作为上下文继续对话

## 图片关键词触发

当用户消息包含以下关键词时，也考虑调用 VL 模型：

- "截图"、"图片"、"图像"
- "看下这个"、"分析这个图"
- "UI"、"界面"、"设计稿"
- "OCR"、"识别文字"