# Local Commander - 本地模型指挥官

> 让你拥有一个本地 AI 团队，实现 90%+ Token 节省

---

## 目录

- [功能概览](#功能概览)
- [快速开始](#快速开始)
  - [一键安装](#一键安装)
  - [验证安装](#验证安装)
  - [基本使用](#基本使用)
- [核心功能](#核心功能)
  - [本地模型调用](#本地模型调用)
  - [代码审查工作流](#代码审查工作流)
  - [AI 知识库](#ai-知识库)
- [UI 自动化测试](#ui-自动化测试)
  - [Web 自动化](#web-自动化)
  - [Android 自动化](#android-自动化)
  - [VL 视觉定位](#vl-视觉定位)
- [高级配置](#高级配置)
  - [模型配置](#模型配置)
  - [VL 服务配置](#vl-服务配置)
- [参考信息](#参考信息)
  - [项目结构](#项目结构)
  - [MCP API 文档](#mcp-api-文档)
  - [常见问题](#常见问题)

---

## 功能概览

### 核心能力

| 能力 | 说明 | 优势 |
|------|------|------|
| 🤖 **本地模型** | 多模型智能路由 | 90%+ Token 节省 |
| 👁️ **图像分析** | VL 视觉理解 | UI 验证、OCR |
| 🧠 **复杂推理** | 35B MoE 模型 | 架构设计、深度分析 |
| 🔄 **代码审查** | 生成→审查→修复 | 自动化质量保证 |

### 模型矩阵

| 模型 | 别名 | 大小 | 专长 |
|------|------|------|------|
| Qwen2.5-Coder-14B | `coder` | 8GB | 代码生成、审查、Debug |
| Qwen2.5-VL-7B | `vl` | 5GB | 图像分析、UI验证、OCR |
| Qwen3.5-35B MoE | `35b` | 18GB | 复杂推理、架构设计 |
| Qwen3-4B | `4b` | 3.5GB | 快速问答、简单代码 |

### 自动化测试

| 平台 | 方案 | 特点 |
|------|------|------|
| Web | Playwright + VL | 截图分析、交互验证 |
| Android | ADB + VL | 零依赖、无需 Appium |
| iOS | XCTest + VL | 模拟器/真机支持 |

---

## 快速开始

### 一键安装

```bash
# 方式一：在线安装
curl -fsSL https://raw.githubusercontent.com/mChenys/local-commander/main/setup.sh | bash

# 方式二：克隆安装
git clone https://github.com/mChenys/local-commander.git
cd local-commander && ./setup.sh
```

安装脚本会自动：
1. 检测系统配置（OS、内存、GPU）
2. 推荐最佳模型组合
3. 安装 Python 依赖
4. 下载推荐模型
5. 配置 MCP 服务

**配置级别**：

| 级别 | 模型组合 | 内存占用 | 适用场景 |
|------|---------|---------|---------|
| `minimal` | 4b + coder | ~12GB | 内存有限 |
| `balanced` | 4b + coder + vl | ~16GB | 日常开发 |
| `standard` | 全部模型 | ~34GB | 全功能使用 |
| `full` | 全部模型 | ~42GB | 内存充裕 |

### 验证安装

```bash
# 验证模型配置
python3 ~/.claude/skills/local-commander/local-commander.py --validate

# 列出可用模型
python3 ~/.claude/skills/local-commander/local-commander.py --models

# 测试知识库
python3 ~/.claude/skills/local-commander/local-commander.py --kb-stats
```

### 基本使用

**CLI 模式**：

```bash
# 激活
/local

# 代码生成
/local 写一个 Kotlin 扩展函数

# 复杂推理
/local --model 35b 设计支付系统架构

# 图像分析
/local --image ~/screenshot.png 分析这个 UI

# 知识库操作
/local --kb-add "Swift 中 @escaping 标记异步闭包"
/local --kb-search "闭包 异步"
```

**MCP 模式**：

```python
# 执行任务
mcp__local-commander-router__execute_local({
    "task": "写一个 TypeScript 函数",
    "model": "coder"  # 可选，自动路由
})

# 代码审查工作流
mcp__local-commander-router__generate_with_review({
    "task": "实现用户登录验证",
    "language": "TypeScript"
})

# 知识库
mcp__local-commander-router__kb_add({
    "text": "知识点内容",
    "category": "coding",
    "tags": ["python", "async"]
})
```

---

## 核心功能

### 本地模型调用

#### 智能路由

系统根据任务特征自动选择最佳模型：

```
┌─────────────────────────────────────────────┐
│              任务输入                        │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│           TaskClassifier                    │
│  ├─ 包含"代码/函数/实现" → coder            │
│  ├─ 包含"图片/截图/UI"   → vl               │
│  ├─ 包含"架构/设计/分析" → 35b              │
│  └─ 简单问答/问候       → 4b                │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│           模型执行                          │
└─────────────────────────────────────────────┘
```

#### MCP 调用

```python
# 基本调用
mcp__local-commander-router__execute_local({
    "task": "任务描述",
    "model": "coder",        # 可选，自动路由
    "max_tokens": 4096,      # 可选
    "smart": true            # 智能模式（自动代码生成）
})

# 返回结果
{
    "success": true,
    "result": "生成的代码或回答",
    "model": "coder",
    "tokens_used": 1234
}
```

### 代码审查工作流

完整的 **生成 → 审查 → 修复** 闭环：

```
┌─────────────────────────────────────────────────────────┐
│                  generate_with_review                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐          │
│   │ coder   │────▶│   35b   │────▶│  coder  │──┐       │
│   │ 生成代码 │     │ 审查代码 │     │ 修复问题 │  │       │
│   └─────────┘     └─────────┘     └─────────┘  │       │
│        │               │               ▲       │       │
│        │               ▼               │       │       │
│        │         ┌───────────┐         │       │       │
│        │         │ 有问题？  │─────────┘       │       │
│        │         └───────────┘                 │       │
│        │               │                       │       │
│        │               ▼ 无问题                │       │
│        │         ┌───────────┐                 │       │
│        └────────▶│ 返回结果  │◀────────────────┘       │
│                  └───────────┘   (最多迭代 2 次)        │
└─────────────────────────────────────────────────────────┘
```

**模型分工**：

| 模型 | 职责 | 原因 |
|------|------|------|
| `coder` | 生成、修复 | 专注代码领域 |
| `35b` | 审查、分析 | MoE + Claude 蒸馏，推理强 |

**MCP 调用**：

```python
# 完整工作流
result = mcp__local-commander-router__generate_with_review({
    "task": "实现用户登录验证",
    "language": "TypeScript",
    "max_fix_iterations": 2
})

# 返回结果
{
    "success": true,
    "final_code": "...修复后的代码...",
    "review_reports": [...],
    "iterations": [...]
}

# 单独审查
mcp__local-commander-router__review_code({
    "code": "...",
    "language": "TypeScript",
    "focus": "all"  # quality / security / performance / all
})

# 单独修复
mcp__local-commander-router__fix_code({
    "code": "...",
    "issues": "问题描述",
    "language": "TypeScript"
})
```

### AI 知识库

基于 BGE-M3 + ChromaDB 的向量知识存储：

```python
# 添加知识点
mcp__local-commander-router__kb_add({
    "text": "知识点内容",
    "category": "coding",      # coding / architecture / debugging / tools / general
    "tags": ["python", "async"],
    "importance": 0.5          # 0-1
})

# 搜索知识
mcp__local-commander-router__kb_search({
    "query": "异步编程",
    "top_k": 5,
    "category": "coding"       # 可选过滤
})

# 列出知识
mcp__local-commander-router__kb_list({
    "category": "coding",
    "tags": ["python"],
    "limit": 20
})

# 删除知识
mcp__local-commander-router__kb_delete({
    "id": "知识点ID"
})

# 统计信息
mcp__local-commander-router__kb_stats({})
```

---

## UI 自动化测试

### Web 自动化

基于 Playwright + VL 的前端验收测试：

```python
# 单页面分析
mcp__local-commander-router__ui_analyze_page({
    "url": "http://localhost:3000/tasks",
    "analysis_prompt": "分析页面功能和问题"
})

# 批量测试
mcp__local-commander-router__ui_test_pages({
    "base_url": "http://localhost:3000",
    "pages": ["/", "/tasks", "/settings"],
    "page_names": ["首页", "任务管理", "设置"]
})

# SPA 路由测试
mcp__local-commander-router__ui_test_spa({
    "url": "http://localhost:1420",
    "routes": [
        {"name": "任务", "menu_text": "任务", "expected_elements": ["新建任务"]},
        {"name": "日志", "menu_text": "日志", "expected_elements": ["导出"]}
    ]
})

# 交互测试
mcp__local-commander-router__ui_interact({
    "url": "http://localhost:3000",
    "steps": [
        {"action": "fill", "selector": "#username", "value": "admin"},
        {"action": "click", "selector": "button[type=submit]"},
        {"action": "assert_text", "selector": ".welcome", "value": "欢迎"}
    ]
})

# 截图
mcp__local-commander-router__ui_screenshot({
    "url": "http://localhost:3000",
    "output_path": "/tmp/screenshot.png"
})
```

### Android 自动化

**零依赖方案**：无需 Appium，直接使用 ADB。

#### 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                  AndroidUIAutomation                     │
├─────────────────────────────────────────────────────────┤
│  基础操作                                                │
│  tap(x, y) | swipe() | input_text() | press_key()       │
├─────────────────────────────────────────────────────────┤
│  元素定位                                                │
│  dump_ui() | find_element() | smart_find()              │
├─────────────────────────────────────────────────────────┤
│  高级操作                                                │
│  tap_element() | scroll_and_find() | run_test_sequence()│
└─────────────────────────────────────────────────────────┘
```

#### MCP 调用

```python
# 获取 UI 元素
mcp__local-commander-router__android_dump_ui({})

# 点击元素（支持多种定位方式）
mcp__local-commander-router__android_tap({
    "text": "登录",                    # 通过文本
    "resource_id": "btn_login",        # 通过 resource-id
    "content_desc": "登录按钮"          # 通过 content-desc
})

# 截图
mcp__local-commander-router__android_screenshot({
    "save_path": "/tmp/screen.png"
})

# 测试序列
mcp__local-commander-router__android_run_test({
    "steps": [
        {"action": "tap", "element": {"text": "设置"}},
        {"action": "screenshot"},
        {"action": "swipe", "x1": 540, "y1": 1500, "x2": 540, "y2": 800},
        {"action": "tap", "element": {"text": "English"}},
        {"action": "assert_element", "element": {"text": "Language"}},
        {"action": "back"},
        {"action": "wait", "seconds": 1}
    ]
})
```

#### 支持的操作

| 操作 | 参数 | 说明 |
|------|------|------|
| `tap` | `element` | 点击元素 |
| `tap_coords` | `x`, `y` | 点击坐标 |
| `smart_tap` | `keyword` | 智能查找点击 |
| `scroll_and_tap` | `keyword` | 滚动查找点击 |
| `input` | `text` | 输入文本 |
| `swipe` | `x1,y1,x2,y2` | 滑动 |
| `back` / `home` | - | 按键 |
| `screenshot` | `save_path` | 截图 |
| `wait` | `seconds` | 等待 |
| `assert_element` | `element` | 断言元素 |
| `assert_text` | `text` | 断言文本 |

### VL 视觉定位

通过自然语言定位 UI 元素，采用**多级降级策略**：

```
dump_ui (ADB精确) → remote_vl (局域网) → local_vl (本地MLX)
     优先级 1            优先级 2            优先级 3
```

| 方法 | 精度 | 速度 | 适用场景 |
|------|------|------|----------|
| `dump_ui` | ⭐⭐⭐⭐⭐ | ~100ms | 文本元素、标准 UI |
| `remote_vl` | ⭐⭐⭐⭐ | ~0.6s | WebView、Canvas、图形 |
| `local_vl` | ⭐⭐⭐ | ~30s | 离线场景 |

#### MCP 调用

```python
# 检测元素
mcp__local-commander-router__vl_detect_element({
    "image_path": "/tmp/screenshot.png",
    "prompt": "蓝色的登录按钮"
})
# 返回: {"elements": [{"label": "登录按钮", "bbox": [...], "center": [x, y]}]}

# 获取点击坐标
mcp__local-commander-router__vl_get_click_coords({
    "image_path": "/tmp/screenshot.png",
    "element_desc": "右上角的设置图标"
})
# 返回: {"x": 200, "y": 380, "confidence": 0.96}

# 智能定位（优先 dump_ui）
mcp__local-commander-router__vl_smart_locate({
    "image_path": "/tmp/screenshot.png",
    "element_desc": "登录",
    "prefer_dump_ui": true
})

# 调试模式
mcp__local-commander-router__vl_debug_detect({
    "image_path": "/tmp/screenshot.png",
    "prompt": "登录按钮",
    "output_path": "/tmp/debug.png"
})
```

#### 与自动化结合

```python
# Android + VL
screenshot = mcp__local-commander-router__android_screenshot({})
coords = mcp__local-commander-router__vl_get_click_coords({
    "image_path": screenshot["screenshot_path"],
    "element_desc": "设置按钮"
})
mcp__local-commander-router__android_tap({"x": coords["x"], "y": coords["y"]})

# Web + VL
mcp__local-commander-router__ui_screenshot({"url": "http://localhost:3000"})
coords = mcp__local-commander-router__vl_get_click_coords({
    "image_path": "/tmp/ui-screenshot.png",
    "element_desc": "提交按钮"
})
```

---

## 高级配置

### 模型配置

配置文件：`~/.claude/skills/local-commander/config/models.json`

```json
{
  "models": {
    "coder": {
      "id": "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
      "alias": "coder",
      "memory_gb": 8,
      "use_cases": ["代码生成", "代码审查", "Debug"],
      "keywords": ["代码", "函数", "实现", "写", "fix"]
    },
    "vl": {
      "id": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
      "alias": "vl",
      "memory_gb": 5,
      "use_cases": ["图像分析", "UI验证", "OCR"],
      "keywords": ["图片", "截图", "图像", "UI", "分析图"]
    },
    "reasoning": {
      "id": "/path/to/your/35b-model",
      "alias": "35b",
      "memory_gb": 18,
      "use_cases": ["复杂推理", "架构设计"],
      "keywords": ["架构", "设计", "方案", "分析"]
    },
    "fast": {
      "id": "/path/to/your/4b-model",
      "alias": "4b",
      "memory_gb": 3.5,
      "use_cases": ["快速对话", "简单代码"],
      "keywords": ["你好", "hello", "快速", "简单"]
    }
  },
  "default_model": "coder",
  "model_groups": {
    "fast_models": ["fast", "coder"],
    "reasoning_models": ["reasoning"],
    "code_models": ["coder", "reasoning"]
  }
}
```

### VL 服务配置

配置文件：`~/.claude/skills/local-commander/config/vl_service.json`

```json
{
  "vl_grounding": {
    "enabled": true,
    "fallback_strategy": "dump_ui -> remote_vl -> local_vl",

    "dump_ui": {
      "enabled": true,
      "priority": 1
    },

    "remote_vl": {
      "enabled": true,
      "priority": 2,
      "base_url": "http://YOUR_SERVER:8000/v1",
      "model": "Qwen/Qwen3-VL-8B-Instruct",
      "api_key": "EMPTY",
      "timeout": 30
    },

    "local_vl": {
      "enabled": true,
      "priority": 3,
      "model": "mlx-community/Qwen2.5-VL-7B-Instruct-bf16",
      "timeout": 180
    }
  }
}
```

**部署 vLLM 服务**（可选）：

```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-VL-8B-Instruct \
    --host 0.0.0.0 --port 8000
```

---

## 参考信息

### 项目结构

```
~/.claude/skills/local-commander/
├── SKILL.md                    # Skill 定义
├── README.md                   # 本文档
├── setup.sh                    # 一键安装脚本
├── local-commander.py          # CLI 入口
├── lib/
│   ├── mcp_router.py           # MCP 服务入口
│   ├── router.py               # 模型路由
│   ├── executor.py             # 任务执行器
│   ├── knowledge_base_chroma.py # ChromaDB 知识库
│   ├── vl_grounding.py         # VL 视觉定位
│   ├── android_ui_automation.py # Android 自动化
│   └── testers/                # 测试器
└── config/
    ├── models.json             # 模型配置
    └── vl_service.json         # VL 服务配置
```

### 数据位置

| 数据 | 位置 |
|------|------|
| MLX 模型 | `~/.cache/huggingface/hub/` |
| 知识库 | `~/.claude/knowledge_chroma/` |

### MCP API 文档

#### 本地模型

| 工具 | 说明 |
|------|------|
| `execute_local` | 执行本地模型任务 |
| `classify_task` | 分析任务类型推荐模型 |
| `route_task` | 路由任务到合适模型 |
| `generate_with_review` | 代码生成+审查+修复 |
| `review_code` | 代码审查 |
| `fix_code` | 代码修复 |

#### 知识库

| 工具 | 说明 |
|------|------|
| `kb_add` | 添加知识点 |
| `kb_search` | 搜索知识 |
| `kb_list` | 列出知识 |
| `kb_delete` | 删除知识 |
| `kb_stats` | 统计信息 |

#### Web 自动化

| 工具 | 说明 |
|------|------|
| `ui_screenshot` | 网页截图 |
| `ui_analyze_page` | 分析页面 |
| `ui_test_pages` | 批量测试 |
| `ui_test_spa` | SPA 路由测试 |
| `ui_interact` | 交互测试 |

#### Android 自动化

| 工具 | 说明 |
|------|------|
| `android_dump_ui` | 获取 UI 元素 |
| `android_tap` | 点击元素 |
| `android_screenshot` | 截图 |
| `android_run_test` | 运行测试序列 |

#### VL 视觉定位

| 工具 | 说明 |
|------|------|
| `vl_detect_element` | 检测元素 |
| `vl_get_click_coords` | 获取点击坐标 |
| `vl_smart_locate` | 智能定位 |
| `vl_service_status` | 服务状态 |

### 常见问题

**Q: 模型下载慢？**
```bash
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download <model>
```

**Q: 内存不足？**
- 使用 4-bit 量化模型
- 只下载需要的模型
- 减少 `max_tokens`

**Q: ChromaDB 报错？**
```bash
pip3 install --break-system-packages --upgrade chromadb
```

**Q: MPS 不可用？**
- 确保 macOS >= 12.3
- 使用 Apple Silicon Mac

**Q: VL 服务连接失败？**
- 检查 `config/vl_service.json` 中的 `base_url`
- 确保 vLLM 服务已启动

---

## 许可证

MIT License

欢迎提交 Issue 和 PR！
