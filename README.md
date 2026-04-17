# Local Commander - 本地模型指挥官

> 让你拥有一个本地 AI 团队，实现 90%+ Token 节省

---

## 目录

- [功能概览](#功能概览)
- [平台支持](#平台支持)
- [快速开始](#快速开始)
  - [一键安装](#一键安装)
  - [手动配置 MCP](#手动配置-mcp)
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

### 平台支持

| 平台 | 后端 | 模型格式 | GPU 加速 |
|------|------|----------|----------|
| Apple Silicon Mac | MLX | MLX 4-bit | Metal ✅ |
| Intel Mac | llama.cpp | GGUF | Metal ✅ |
| Linux (NVIDIA) | llama.cpp | GGUF | CUDA ✅ |
| Linux (CPU) | llama.cpp | GGUF | - |

### 模型矩阵

**Apple Silicon (MLX)**：

| 模型 | 别名 | 大小 | 专长 |
|------|------|------|------|
| Qwen2.5-Coder-14B | `coder` | 8GB | 代码生成、审查、Debug |
| Qwen2.5-VL-7B | `vl` | 5GB | 图像分析、UI验证、OCR |
| Qwen3.5-35B MoE | `35b` | 18GB | 复杂推理、架构设计 |
| Qwen3-4B | `4b` | 3.5GB | 快速问答、简单代码 |

**Intel Mac / Linux (llama.cpp GGUF)**：

| 模型 | 别名 | 大小 | 专长 |
|------|------|------|------|
| Gemma-4-E2B | `mini` | 3.5GB | 快速对话、图像分析 (多模态) |
| Gemma-4-E4B | `fast` | 5.5GB | 对话、图像分析、OCR (多模态) |
| Qwen2.5-Coder-7B | `coder` | 5GB | 代码生成、审查 |

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
3. 安装 Python 依赖和 llama.cpp（Intel Mac）
4. 下载推荐模型
5. 配置 MCP 服务

**配置级别**：

**Apple Silicon (MLX)**：

| 级别 | 模型组合 | 内存占用 | 适用场景 |
|------|---------|---------|---------|
| `minimal` | 4b + coder | ~12GB | 内存有限 |
| `balanced` | 4b + coder + vl | ~16GB | 日常开发 |
| `standard` | 全部模型 | ~34GB | 全功能使用 |

**Intel Mac (llama.cpp GGUF)**：

| 级别 | 模型组合 | 内存占用 | 适用场景 |
|------|---------|---------|---------|
| `mini` | E2B 多模态 | ~4GB | 内存有限 |
| `balanced` | E2B + E4B + coder | ~14GB | 日常开发 |
| `standard` | E4B + coder | ~11GB | 内存充足 |

### 手动配置 MCP

如果安装脚本没有成功配置 MCP，请手动执行：

```bash
# 删除旧配置（如果存在）
claude mcp remove local-commander-router 2>/dev/null

# 添加 MCP 服务器
claude mcp add \
  -e "LOCAL_COMMANDER_PATH=$HOME/.claude/skills/local-commander" \
  -e "LOCAL_COMMANDER_BACKEND=llamacpp" \
  -- local-commander-router python3 "$HOME/.claude/skills/local-commander/lib/mcp_router.py"

# 验证配置
claude mcp list
```

> **注意**：Intel Mac 使用 `llamacpp`，Apple Silicon 使用 `mlx`（或省略，自动检测）

### 验证安装

```bash
# 验证模型配置
python3 ~/.claude/skills/local-commander/local-commander.py --validate

# 列出可用模型
python3 ~/.claude/skills/local-commander/local-commander.py --models

# 测试知识库
python3 ~/.claude/skills/local-commander/local-commander.py --kb-stats
```

### 强制指定后端

可以通过环境变量强制指定后端（用于测试）：

```bash
# 强制使用 llama.cpp 后端
LOCAL_COMMANDER_BACKEND=llamacpp python3 ~/.claude/skills/local-commander/local-commander.py "你好"

# 强制使用 MLX 后端
LOCAL_COMMANDER_BACKEND=mlx python3 ~/.claude/skills/local-commander/local-commander.py "你好"
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

# 截图
mcp__local-commander-router__ui_screenshot({
    "url": "http://localhost:3000",
    "output_path": "/tmp/screenshot.png"
})
```

### Android 自动化

#### 方案对比

| 方案 | 启动耗时 | 权限弹窗 | 视觉识别 | 安装依赖 |
|------|---------|---------|---------|---------|
| **uiautomator2 (推荐)** | ~2s | ✅ 内置 | ✅ VL协同 | 仅 Python |
| Appium | 10-30s | ⚠️ 需配置 | ❌ 需额外 | Node.js + Server |

**为什么不需要 Appium？**

```
Appium 架构:                          uiautomator2 架构:
Python → Appium Client →              Python → uiautomator2 →
Appium Server (Node.js) →             ATX Agent → Android
UiAutomator2 → Android                (直接连接，无中间层)
(多层架构，启动慢)                      (单层架构，启动快)
```

#### 安装依赖

```bash
# 安装 uiautomator2
pip3 install uiautomator2

# 在手机上安装 ATX Agent（首次需要）
python3 -m uiautomator2 init
```

#### 混合自动化架构

**核心原则：uiautomator2 优先，VL 视觉模型降级辅助**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          元素定位请求                                    │
│                    hybrid_tap("登录按钮")                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  Step 1: uiautomator2 定位     │
                    │  耗时: ~0.3s                   │
                    │                               │
                    │  ① d(text="登录")             │
                    │  ② d(textContains="登录")     │
                    │  ③ d(description="登录")      │
                    │  ④ d(resourceId="btn_login")  │
                    └───────────────────────────────┘
                           │              │
                        找到 ✅          未找到 ❌
                           │              │
                           ▼              ▼
                    ┌──────────┐   ┌───────────────────────────────┐
                    │ 返回结果  │   │  Step 2: VL 视觉定位 (降级)   │
                    │ 点击元素  │   │  耗时: ~15-20s                 │
                    └──────────┘   │                               │
                                   │  ① 截图当前屏幕                │
                                   │  ② VL 分析："找出登录按钮位置" │
                                   │  ③ 返回坐标 (x, y)            │
                                   │  ④ 点击坐标                    │
                                   └───────────────────────────────┘
```

#### 适用场景分工

| 场景 | 主力工具 | 耗时 | 原因 |
|------|---------|------|------|
| 有文本的按钮 | uiautomator2 | ~0.3s | 快速、精确 |
| 有 resource-id | uiautomator2 | ~0.3s | 稳定可靠 |
| **系统权限弹窗** | uiautomator2 | <0.5s | 结构化定位，不受 UI 样式影响 |
| 滚动查找元素 | uiautomator2 | ~2s | 内置滚动支持 |
| **图标按钮（无文字）** | VL 视觉 | ~20s | u2 无法定位 |
| **自定义控件** | VL 视觉 | ~20s | 没有 ID/文本 |
| UI 验证截图 | VL 视觉 | ~20s | 需要语义理解 |

#### Uiautomator2 MCP 工具

```python
# 初始化连接
mcp__local-commander-router__u2_init({})
# 返回: {"success": true, "device": "xxx", "display_width": 1080, ...}

# 处理系统权限弹窗（核心功能）
mcp__local-commander-router__u2_handle_permission({
    "action": "allow",        # allow | deny | dismiss
    "wait_timeout": 5
})

# 智能点击元素（自动等待）
mcp__local-commander-router__u2_smart_tap({
    "keyword": "登录",
    "timeout": 5
})

# 滚动查找并点击
mcp__local-commander-router__u2_scroll_and_tap({
    "keyword": "登出",
    "direction": "down",      # up | down
    "max_scrolls": 5
})

# 输入文本
mcp__local-commander-router__u2_input_text({
    "element_keyword": "手机号",
    "text": "18819444345",
    "clear_first": true
})

# 完整登录测试（自动处理权限）
mcp__local-commander-router__u2_run_login_test({
    "phone": "18819444345",
    "code": "112233",
    "auto_handle_permissions": true
})
```

#### 原始 ADB 工具（兼容旧方案）

```python
# 获取 UI 元素
mcp__local-commander-router__android_dump_ui({})

# 点击元素（支持多种定位方式）
mcp__local-commander-router__android_tap({
    "text": "登录",
    "resource_id": "btn_login",
    "content_desc": "登录按钮"
})

# 截图
mcp__local-commander-router__android_screenshot({
    "save_path": "/tmp/screen.png"
})

# 测试序列
mcp__local-commander-router__android_run_test({
    "steps": [
        {"action": "tap", "element": {"text": "设置"}},
        {"action": "smart_tap", "keyword": "English"},
        {"action": "scroll_and_tap", "keyword": "登出"},
        {"action": "screenshot"}
    ]
})
```

#### Python 直接调用

```python
import uiautomator2 as u2

d = u2.connect()

# 基础操作
d(text="登录").click()
d(resourceId="btn_login").click()
d(description="允许").click()  # 权限弹窗

# 滚动查找
d(scrollable=True).scroll.to(text="登出")
d(text="登出").click()

# 输入
d(resourceId="input").set_text("hello")

# 等待
d(text="加载完成").wait(timeout=10)
```

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
| `local_vl` | ⭐⭐⭐ | ~15s | 离线场景 |

#### VL 视觉分析

```python
# UI 验证 - 检查网络状态
vl.detect_element(screenshot, "页面顶部是否有断网提示？")

# OCR 文字提取
vl.detect_element(screenshot, "提取页面上的所有文字")

# 元素坐标定位
vl.detect_element(screenshot, "找出蓝色发送按钮的位置")
# 返回: {"success": true, "center": [x, y]}
```

#### 与 uiautomator2 协同

```python
# 推荐：混合自动化，自动降级
from android_hybrid_automation import AndroidHybridAutomation

hybrid = AndroidHybridAutomation()
hybrid.set_vl_service(vl_service)

# 智能点击（先 u2，失败自动降级 VL）
result = hybrid.hybrid_tap("登录按钮")

# UI 验证
result = hybrid.check_network_status()  # 检查断网提示
result = hybrid.check_error_dialog()     # 检查错误弹窗
```

---

## 高级配置

### 模型配置

配置文件：`~/.claude/skills/local-commander/config/models.json`

**Apple Silicon (MLX)**：

```json
{
  "backend": "mlx",
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
    }
  },
  "default_model": "coder"
}
```

**Intel Mac (llama.cpp GGUF)**：

```json
{
  "backend": "llamacpp",
  "models": {
    "mini": {
      "hf_repo": "unsloth/gemma-4-E2B-it-GGUF",
      "gguf_file": "gemma-4-E2B-it-Q4_K_M.gguf",
      "mmproj_file": "mmproj-BF16.gguf",
      "alias": "mini",
      "memory_gb": 3.5,
      "is_multimodal": true
    },
    "fast": {
      "hf_repo": "unsloth/gemma-4-E4B-it-GGUF",
      "gguf_file": "gemma-4-E4B-it-Q4_K_M.gguf",
      "mmproj_file": "mmproj-BF16.gguf",
      "alias": "fast",
      "memory_gb": 5.5,
      "is_multimodal": true
    },
    "coder": {
      "hf_repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
      "gguf_file": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
      "alias": "coder",
      "memory_gb": 5
    }
  },
  "default_model": "fast"
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
│   ├── backends/               # 后端实现
│   │   ├── __init__.py         # 后端检测
│   │   ├── mlx_backend.py      # MLX 后端 (Apple Silicon)
│   │   └── llamacpp_backend.py # llama.cpp 后端 (Intel Mac/Linux)
│   ├── knowledge_base_chroma.py # ChromaDB 知识库
│   ├── vl_grounding.py         # VL 视觉定位
│   ├── android_ui_automation.py # Android 自动化 (ADB)
│   ├── android_u2_automation.py # Android 自动化 (uiautomator2) ⭐ 新增
│   ├── android_hybrid_automation.py # 混合自动化 (u2 + VL) ⭐ 新增
│   └── testers/                # 测试器
└── config/
    ├── models.json             # 模型配置
    └── vl_service.json         # VL 服务配置
```

### 数据位置

| 数据 | 位置 |
|------|------|
| MLX 模型 | `~/.cache/huggingface/hub/` |
| GGUF 模型 | `~/.cache/huggingface/hub/models--*/snapshots/` |
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
| **`u2_init`** | 初始化 uiautomator2 连接 ⭐ |
| **`u2_handle_permission`** | 处理系统权限弹窗 ⭐ |
| **`u2_smart_tap`** | 智能点击元素 ⭐ |
| **`u2_scroll_and_tap`** | 滚动查找并点击 ⭐ |
| **`u2_input_text`** | 输入文本 ⭐ |
| **`u2_run_login_test`** | 完整登录测试 ⭐ |

#### VL 视觉定位

| 工具 | 说明 |
|------|------|
| `vl_detect_element` | 检测元素 |
| `vl_get_click_coords` | 获取点击坐标 |
| `vl_smart_locate` | 智能定位 |
| `vl_service_status` | 服务状态 |

### 常见问题

**Q: MCP 配置不生效？**

手动配置 MCP：
```bash
claude mcp remove local-commander-router 2>/dev/null
claude mcp add \
  -e "LOCAL_COMMANDER_PATH=$HOME/.claude/skills/local-commander" \
  -e "LOCAL_COMMANDER_BACKEND=llamacpp" \
  -- local-commander-router python3 "$HOME/.claude/skills/local-commander/lib/mcp_router.py"
```

**Q: 模型下载慢？**
```bash
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download <model>
```

**Q: Intel Mac llama.cpp 安装失败？**
```bash
brew install llama.cpp
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

**Q: uiautomator2 连接失败？**
```bash
# 重新安装 ATX Agent
python3 -m uiautomator2 init

# 检查设备连接
adb devices
```

**Q: 系统权限弹窗处理不了？**
- 使用 `u2_handle_permission` 工具
- 确保 uiautomator2 已正确初始化
- 对于特殊厂商弹窗，可能需要自定义处理逻辑

**Q: 需要安装 Appium 吗？**
- **不需要！** uiautomator2 已足够强大
- uiautomator2 启动更快（~2s vs Appium 10-30s）
- 权限弹窗处理更简单
- 与 VL 视觉模型协同工作

---

## 许可证

MIT License

欢迎提交 Issue 和 PR！
