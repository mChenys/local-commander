---
name: local
description: >
  本地模型指挥官 - 让你拥有一个本地 AI 团队。
  调用本地 MLX 模型执行代码生成、图像分析等任务，实现 90%+ Token 节省。

  激活: /local
  退出: /local exit
  状态: /local status

  使用示例:
  - /local 你好
  - /local 写一个 Kotlin 扩展函数
  - /local --model coder 帮我写个 Swift 类

  图片分析（自动触发）:
  - 用户粘贴图片时，自动调用本地 VL 模型分析
  - 无需手动进入 /local 模式

  🆕 MCP 自动路由:
  - 通过 MCP 服务自动识别任务类型
  - 无需手动指定模型
---

# Local Commander - 本地模型指挥官

## ⚠️ 首次使用必须安装

**如果这是你第一次使用，请先完成以下安装步骤：**

### 1. 安装依赖

```bash
pip3 install --break-system-packages \
    mlx mlx-lm mlx-vlm \
    sentence-transformers \
    chromadb \
    numpy
```

### 2. 配置 MCP 服务

编辑 `~/.claude/.mcp.json`，添加以下配置：

```json
{
  "mcpServers": {
    "local-commander-router": {
      "command": "python3",
      "args": ["/Users/<你的用户名>/.claude/skills/local-commander/lib/mcp_router.py"],
      "env": {
        "LOCAL_COMMANDER_PATH": "/Users/<你的用户名>/.claude/skills/local-commander"
      }
    }
  }
}
```

### 3. 验证安装

```bash
python3 ~/.claude/skills/local-commander/local-commander.py --validate
```

### 4. 首次使用会自动下载模型

模型会自动下载到 `~/.cache/huggingface/hub/`，首次使用时需要等待下载完成。

---

**详细文档请阅读 README.md**

## 🆕 MCP 自动路由模式（推荐）

**现在支持通过 MCP 服务自动识别任务类型并路由到合适的本地模型！**

### 自动触发条件

| 任务类型 | 自动路由模型 | 触发关键词 |
|---------|------------|-----------|
| 代码生成 | `coder` | 代码、编程、Kotlin、Swift、函数、类、实现、写、生成、bug、debug |
| 图像分析 | `vl` | 图片、截图、图像、UI、界面、分析图、OCR |
| 复杂推理 | `27b` | 架构、设计、方案、分析、评估、解释 |
| 快速问答 | `7b` | 你好、hello、hi、谢谢、快速、简单 |

### MCP 服务调用方式

```python
# 方法1: 分类任务 - 返回推荐模型
{"method": "classify", "task": "帮我写一个 Swift 函数"}
# 返回: {"recommended_model": "coder", "confidence": 0.85}

# 方法2: 执行任务 - 自动选择模型并执行
{"method": "execute", "task": "写一个 Kotlin 扩展函数"}
# 返回: {"success": true, "output": "...", "model_used": "coder"}
```

### MCP 服务文件位置
- 配置: `~/.claude/skills/local-commander/mcp_config.json`
- 服务: `~/.claude/skills/local-commander/lib/mcp_router.py`

---

## 自动图片路由（重要！）

**当用户粘贴图片（Ctrl+V）或提供图片路径时，自动执行：**

```bash
python3 ~/.claude/skills/local-commander/local-commander.py --image "<图片路径>" "分析这张图片的内容"
```

**检测图片的模式：**
- 路径以 `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp` 结尾
- 路径包含 `/tmp/`, `Downloads/`, `Desktop/` 等目录
- 用户说 "截图"、"图片"、"看下这个"

**示例场景：**
1. 用户粘贴截图 → 自动调用 VL 模型分析 → 继续对话
2. 用户提供图片路径 → 分析图片 → 回答问题
3. 用户问 "这个UI怎么样" + 粘贴图片 → 分析UI并给出建议

## 执行规则

当用户输入 `/local <任务>` 时，**直接执行以下命令**：

```bash
python3 ~/.claude/skills/local-commander/local-commander.py "<任务>"
```

**不要**使用复杂的 Python 脚本或 subprocess，直接调用 CLI 工具。

## 可用模型

| 别名 | 模型 | 用途 |
|------|------|------|
| `coder` | Qwen2.5-Coder-14B | 代码生成、审查、Debug |
| `vl` | Qwen2.5-VL-7B | 图像分析、UI验证、OCR |
| `27b` | Qwen3.5-27B | 复杂推理、架构设计 |
| `7b` | Qwen2.5-7B | 轻量对话、快速回答 |

## 新增功能

### 1. 系统诊断与验证
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --validate  # 验证模型配置
python3 ~/.claude/skills/local-commander/local-commander.py --system-info  # 显示系统信息
python3 ~/.claude/skills/local-commander/local-commander.py --models  # 列出可用模型
python3 ~/.claude/skills/local-commander/local-commander.py --benchmark  # 基准测试模型
python3 ~/.claude/skills/local-commander/local-commander.py --optimize  # 优化配置
```

### 2. 增强的项目分析
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --analyze --scan-depth deep  # 深度扫描项目
```

支持三种扫描深度：
- `light`: 轻量扫描（最多50个文件，适合快速分析）
- `normal`: 标准扫描（最多200个文件，默认）
- `deep`: 深度扫描（最多1000个文件，包含完整符号分析）

### 3. 测试增强功能
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --test --test-device "emulator-5554"  # 指定设备测试
python3 ~/.claude/skills/local-commander/local-commander.py --test --test-target "com.example.app"  # 指定测试目标
```

## 测试功能

Local Commander 现在支持自动化测试功能，可对 Android、iOS 和 Web 项目运行不同类型测试：

**运行自动化测试：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --test
```

**指定测试类型：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --test --test-type espresso  # Android Espresso
python3 ~/.claude/skills/local-commander/local-commander.py --test --test-type playwright  # Web Playwright
python3 ~/.claude/skills/local-commander/local-commander.py --test --test-type xctest  # iOS XCTest
```

**与代码生成结合（智能模式）：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --smart --test "帮我改进登录页面"
```

## 执行示例

**普通任务：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py "你好"
```

**指定模型：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --model coder "写一个 Kotlin 函数"
```

**图像分析：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --image ~/Downloads/screenshot.png "分析这个UI"
```

**运行项目测试：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --test  # 自动检测项目类型并运行测试
```

**智能模式（带上下文和测试）：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --smart --test "优化应用性能"
```

**系统验证：**
```bash
python3 ~/.claude/skills/local-commander/local-commander.py --validate  # 验证配置
python3 ~/.claude/skills/local-commander/local-commander.py --benchmark  # 模型基准测试
python3 ~/.claude/skills/local-commander/local-commander.py --optimize  # 优化配置
```

## 命令格式

| 命令 | 执行 |
|------|------|
| `/local <任务>` | `python3 ~/.claude/skills/local-commander/local-commander.py "<任务>"` |
| `/local --model <名> <任务>` | `python3 ~/.claude/skills/local-commander/local-commander.py --model <名> "<任务>"` |
| `/local --image <路径> <任务>` | `python3 ~/.claude/skills/local-commander/local-commander.py --image <路径> "<任务>"` |
| `/local --smart <任务>` | `python3 ~/.claude/skills/local-commander/local-commander.py --smart "<任务>"` (智能模式，带项目上下文) |
| `/local --test` | `python3 ~/.claude/skills/local-commander/local-commander.py --test` (运行自动化测试) |
| `/local --test --test-type <类型>` | `python3 ~/.claude/skills/local-commander/local-commander.py --test --test-type <类型>` (指定测试类型) |
| `/local --smart --test <任务>` | `python3 ~/.claude/skills/local-commander/local-commander.py --smart --test "<任务>"` (智能模式+测试) |
| `/local --validate` | `python3 ~/.claude/skills/local-commander/local-commander.py --validate` (验证模型配置) |
| `/local --benchmark` | `python3 ~/.claude/skills/local-commander/local-commander.py --benchmark` (模型基准测试) |
| `/local --optimize` | `python3 ~/.claude/skills/local-commander/local-commander.py --optimize` (优化配置) |
| `/local --models` | `python3 ~/.claude/skills/local-commander/local-commander.py --models` (列出可用模型) |
| `/local --system-info` | `python3 ~/.claude/skills/local-commander/local-commander.py --system-info` (显示系统信息) |
| `/local --analyze --scan-depth deep` | `python3 ~/.claude/skills/local-commander/local-commander.py --analyze --scan-depth deep` (深度分析项目) |
| `/local status` | `python3 ~/.claude/skills/local-commander/local-commander.py --status` |
| `/local --help` | `python3 ~/.claude/skills/local-commander/local-commander.py --help` (显示详细帮助) |
| `/local exit` | 结束会话（无需执行命令） |

## 自动路由关键词

- **coder**: 代码、编程、Kotlin、Swift、函数、类、实现、写、生成
- **vl**: 图片、截图、图像、UI、界面、分析图、看
- **reasoning**: 架构、设计、方案、分析、评估、解释
- **fast**: 你好、hello、hi、谢谢、快速、简单

---

## 🆕 代码审查工作流（推荐）

### 完整工作流：生成 → 审查 → 修复

```python
# MCP 工具调用
mcp__local-commander-router__generate_with_review({
    "task": "实现一个用户登录验证函数",
    "language": "TypeScript",
    "max_fix_iterations": 2
})
```

**工作流程：**
```
1. coder 模型生成代码
2. 27b 模型审查代码
3. 如果发现问题 → coder 模型修复
4. 重复步骤 2-3 直到通过或达到最大迭代次数
5. 返回最终代码和审查报告
```

### 单独使用审查

```python
# 审查已有代码
mcp__local-commander-router__review_code({
    "code": "... 你的代码 ...",
    "language": "TypeScript",
    "focus": "all"  # quality / security / performance / all
})
```

### 单独使用修复

```python
# 修复已知问题
mcp__local-commander-router__fix_code({
    "code": "... 原始代码 ...",
    "issues": "... 审查报告中的问题 ...",
    "language": "TypeScript"
})
```

### 模型分工

| 模型 | 职责 | 适用场景 |
|------|------|----------|
| `coder` | 代码生成、修复 | 写代码、Debug、重构 |
| `27b` | 代码审查、架构分析 | 质量检查、方案评估 |
| `vl` | 图像分析 | 截图分析、UI验证 |
| `7b` | 快速问答 | 简单问题、快速响应 |

---

## 🆕 UI 自动化验收测试（前端开发必备）

**前端开发闭环：写代码 → 自动截图 → VL 模型分析 → 发现问题 → 自动修复**

### 使用场景

- 前端页面开发完成后自动验收
- 检测 UI 是否正常渲染
- 发现功能问题和 UI 缺陷
- 批量测试多个页面

### 1. 单页面分析

```python
# 截图并用 VL 模型分析页面
mcp__local-commander-router__ui_analyze_page({
    "url": "http://localhost:3000/tasks",
    "analysis_prompt": "分析这个页面的功能和问题"
})
```

返回：
- 页面截图路径
- VL 模型的分析结果
- 功能、布局、问题描述

### 2. 批量页面测试

```python
# 测试整个应用的所有页面
mcp__local-commander-router__ui_test_pages({
    "base_url": "http://localhost:3000",
    "pages": ["/", "/tasks", "/logs", "/settings"],
    "page_names": ["首页", "任务管理", "日志监控", "设置"]
})
```

返回：
- 每个页面的分析结果
- 通过/失败统计
- 问题汇总

### 3. 仅截图

```python
# 只截图不分析
mcp__local-commander-router__ui_screenshot({
    "url": "http://localhost:3000",
    "output_path": "/tmp/screenshot.png",
    "viewport_width": 1400,
    "viewport_height": 900
})
```

### 4. 交互测试

```python
# 点击按钮并验证结果
mcp__local-commander-router__ui_click_and_verify({
    "url": "http://localhost:3000/tasks",
    "selector": "button.new-task",
    "verify_type": "screenshot",  # 或 "text", "element"
    "verify_target": "弹窗是否出现"
})
```

### 工作流示例

```
1. 开发前端页面
2. 调用 ui_analyze_page 自动验收
3. VL 模型发现问题
4. 调用 coder 模型修复代码
5. 再次验收确认修复
```

### 技术原理

```
Playwright (浏览器自动化) → 截图 → VL 视觉模型 (图像理解) → 分析报告
```

---

## 🆕 AI 知识库 (ChromaDB)

**持久化知识存储，支持语义搜索，跨会话记忆学习到的知识。**

### 命令

| 命令 | 说明 |
|------|------|
| `/local --kb-add <内容>` | 添加知识点 |
| `/local --kb-search <查询>` | 语义搜索 |
| `/local --kb-list` | 列出知识点 |
| `/local --kb-stats` | 统计信息 |

### MCP 工具调用

```python
# 添加知识点
mcp__local-commander-router__kb_add({
    "text": "知识点内容",
    "category": "coding",  # coding/architecture/debugging/tools/concepts/general
    "tags": ["python", "async"],
    "importance": 0.8
})

# 语义搜索
mcp__local-commander-router__kb_search({
    "query": "RAG 向量搜索",
    "top_k": 5,
    "category": "coding"  # 可选过滤
})

# 列出知识点
mcp__local-commander-router__kb_list({"limit": 20})

# 统计信息
mcp__local-commander-router__kb_stats({})

# 删除知识点
mcp__local-commander-router__kb_delete({"id": "kb_xxx"})
```

### 知识点分类

| 分类 | 说明 |
|------|------|
| `coding` | 代码技巧、最佳实践 |
| `architecture` | 架构设计、系统设计 |
| `debugging` | 调试技巧、问题解决 |
| `tools` | 工具使用、配置 |
| `concepts` | 概念解释、理论知识 |
| `general` | 通用知识 |

### 底层实现

- **向量数据库**: ChromaDB (HNSW 索引)
- **Embedding 模型**: BGE-M3 (1024 维向量)
- **存储位置**: `~/.claude/knowledge_chroma/`

---

## 🆕 全平台 UI 自动化测试

**Local Commander 现已支持 Web、桌面、Android、iOS 全平台 UI 自动化测试！**

### 支持的平台

| 平台 | 工具 | 依赖 |
|------|------|------|
| 🌐 Web/SPA | `ui_screenshot`, `ui_analyze_page`, `ui_test_pages` | Playwright |
| 🖥️ macOS 原生窗口 | `native_window_list`, `native_window_query` | AppleScript |
| 📱 Android | `android_screenshot`, `android_tap`, `android_run_test` | ADB |
| 🍎 iOS 模拟器 | `ios_simulator_*` 系列工具 | Xcode |
| 🍎 iOS 真机 | `ios_device_*` 系列工具 | libimobiledevice |
| 🔗 API 测试 | `api_request`, `api_test_sequence` | requests |

---

### iOS 模拟器测试

```python
# 列出所有模拟器
mcp__local-commander-router__ios_simulator_list({"state": "all"})  # all/booted/shutdown

# 启动模拟器
mcp__local-commander-router__ios_simulator_control({
    "action": "boot",  # boot/shutdown/restart
    "device": "iPhone 16 Pro"
})

# 截取模拟器屏幕
mcp__local-commander-router__ios_simulator_screenshot({
    "save_path": "/tmp/ios-screenshot.png"
})

# 模拟器操作
mcp__local-commander-router__ios_simulator_action({
    "action": "tap",  # tap/swipe/input/key
    "x": 100,
    "y": 200
})

# 应用管理
mcp__local-commander-router__ios_simulator_app({
    "action": "install",  # install/launch/uninstall
    "app_path": "/path/to/App.app"
})
```

### iOS 真机测试

**先安装依赖：**
```bash
brew install libimobiledevice
```

```python
# 列出连接的设备
mcp__local-commander-router__ios_device_list({})

# 截取真机屏幕
mcp__local-commander-router__ios_device_screenshot({
    "save_path": "/tmp/ios-device.png"
})
```

---

### macOS 原生窗口测试

```python
# 列出所有窗口
mcp__local-commander-router__native_window_list({
    "app_name": "Safari"  # 可选过滤
})

# 查询窗口元素
mcp__local-commander-router__native_window_query({
    "app_name": "Finder",
    "query_type": "buttons"  # buttons/texts/checkboxes/menus/all
})
```

---

### API 测试

```python
# 单个 API 请求
mcp__local-commander-router__api_request({
    "method": "GET",
    "url": "https://api.example.com/users",
    "headers": {"Authorization": "Bearer xxx"},
    "expected_status": 200
})

# API 测试序列
mcp__local-commander-router__api_test_sequence({
    "name": "用户流程测试",
    "requests": [
        {"method": "POST", "url": "/login", "body": {...}},
        {"method": "GET", "url": "/profile"},
        {"method": "DELETE", "url": "/logout"}
    ],
    "base_url": "https://api.example.com",
    "stop_on_failure": true
})
```

---

### 完整测试平台架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    🎉 Local Commander MCP - 全平台 UI 自动化测试                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  🌐 Web/SPA          🖥️ 桌面应用          📱 Android          🍎 iOS            │
│  ─────────────       ─────────────        ─────────────       ─────────────    │
│  ✅ ui_screenshot    ✅ native_window_*   ✅ android_*        ✅ ios_simulator_* │
│  ✅ ui_analyze_page  ✅ AppleScript       ✅ 截图              ✅ 模拟器控制       │
│  ✅ ui_test_pages    ✅ 窗口元素查询       ✅ 点击              ✅ 应用管理         │
│  ✅ VL 视觉分析                          ✅ 录制测试          ✅ ios_device_*    │
│                                         ✅ VL 视觉分析       ✅ 真机截图         │
│                                                                                 │
│  🔗 API 测试          📊 测试报告                                            │
│  ─────────────        ─────────────                                           │
│  ✅ api_request       ✅ ui_generate_report                                   │
│  ✅ api_test_sequence                                                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```