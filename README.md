# Local Commander - 本地模型指挥官

> 让你拥有一个本地 AI 团队，实现 90%+ Token 节省

## 功能概览

| 功能 | 模型 | 说明 |
|------|------|------|
| 🤖 代码生成 | Qwen2.5-Coder-14B | 生成、审查、Debug |
| 👁️ 图像分析 | Qwen2.5-VL-7B | UI验证、OCR、截图分析 |
| 🧠 复杂推理 | Qwen3.5-27B | 架构设计、方案评估 |
| ⚡ 快速问答 | Qwen2.5-7B | 轻量对话 |
| 📚 AI 知识库 | BGE-M3 + ChromaDB | 持久化知识存储 |
| 🧪 Web 自动化测试 | Playwright + VL | UI 自动化验收测试 |
| 📱 Android 自动化 | ADB + VL | 无需 Appium 的 UI 测试 |
| 🔄 代码审查流 | Coder + 27B | 生成 → 审查 → 修复 |

---

## 快速开始

### 1. 系统要求

- **操作系统**: macOS (Apple Silicon 推荐)
- **Python**: 3.10+
- **内存**: 16GB+ (推荐 32GB)
- **存储**: 50GB+ (用于模型)

### 2. 安装依赖

```bash
# Python 依赖
pip3 install --break-system-packages \
    mlx mlx-lm mlx-vlm \
    sentence-transformers \
    chromadb \
    numpy

# Node.js 依赖 (用于 UI 自动化测试，可选)
npm install -g playwright
npx playwright install
```

### 3. 下载本地模型

#### MLX 模型 (代码/推理/视觉)

使用 [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) 项目提供的 **4-bit 量化模型**：

```bash
# 安装 mlx-vlm (如果还没安装)
pip3 install --break-system-packages mlx-vlm

# 首次使用时会自动下载模型到 ~/.cache/huggingface/hub/
# 无需手动下载，执行任务时自动拉取
```

**可用模型 (自动下载):**

| 别名 | 模型 ID | 大小 | 用途 |
|------|---------|------|------|
| `coder` | `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` | ~8GB | 代码生成 |
| `vl` | `mlx-community/Qwen2.5-VL-7B-Instruct-4bit` | ~5GB | 图像分析 |
| `27b` | `mlx-community/Qwen3.5-27B-4bit` | ~15GB | 复杂推理 |
| `7b` | `mlx-community/Qwen2.5-7B-Instruct-4bit` | ~4GB | 快速问答 |

#### 🔄 模型自动下载机制

**无需手动下载模型！** 模型会在首次使用时自动下载：

```
用户执行命令 (如 /local 写代码)
       ↓
local-commander.py 调用 mlx-vlm 库
       ↓
mlx-vlm 检查模型是否已存在于本地缓存
       ↓
┌─────────────────────────────────────┐
│ 不存在 → 自动从 HuggingFace 下载     │
│          到 ~/.cache/huggingface/    │
│ 存在   → 直接加载，无需等待          │
└─────────────────────────────────────┘
```

**按需下载特点：**

| 特点 | 说明 |
|------|------|
| 🎯 **按需下载** | 只下载实际用到的模型，不用的不下载 |
| 🤖 **自动触发** | 执行任务时代码自动下载，无需手动操作 |
| 💾 **持久化** | 下载后保存在本地，下次启动秒加载 |
| 📦 **增量更新** | 只下载变更部分，节省带宽 |

**下载触发时机：**

| 首次执行 | 自动下载模型 |
|---------|------------|
| `/local 你好` | `7b` (~4GB) |
| `/local 写代码` | `coder` (~8GB) |
| `/local --image xxx 分析图片` | `vl` (~5GB) |
| `/local --model 27b 复杂问题` | `27b` (~15GB) |

**模型存储位置：**

```
~/.cache/huggingface/hub/
├── models--mlx-community--Qwen2.5-Coder-14B-Instruct-4bit/   # 代码模型
├── models--mlx-community--Qwen2.5-VL-7B-Instruct-4bit/       # 视觉模型
├── models--mlx-community--Qwen3.5-27B-4bit/                  # 推理模型
├── models--mlx-community--Qwen2.5-7B-Instruct-4bit/          # 快速模型
└── models--BAAI--bge-m3/                                      # Embedding 模型
```

**手动预下载 (可选，节省首次等待时间):**

```bash
# 使用 Python 预下载模型
python3 -c "from mlx_vlm import load; load('mlx-community/Qwen2.5-Coder-14B-Instruct-4bit')"
python3 -c "from mlx_vlm import load; load('mlx-community/Qwen2.5-VL-7B-Instruct-4bit')"
python3 -c "from mlx_vlm import load; load('mlx-community/Qwen3.5-27B-4bit')"
python3 -c "from mlx_vlm import load; load('mlx-community/Qwen2.5-7B-Instruct-4bit')"
```

#### Embedding 模型 (知识库)

```bash
# BGE-M3 会自动下载到 ~/.cache/huggingface/hub/
# 首次使用知识库时自动下载，无需手动操作
```

### 4. 安装 Local Commander

```bash
# 复制到 Claude Code skills 目录
cp -r local-commander ~/.claude/skills/

# 添加执行权限
chmod +x ~/.claude/skills/local-commander/local-commander.py
```

### 5. 配置 MCP 服务

创建或编辑 `~/.claude/.mcp.json`:

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

### 6. 验证安装

```bash
# 验证模型配置
python3 ~/.claude/skills/local-commander/local-commander.py --validate

# 列出可用模型
python3 ~/.claude/skills/local-commander/local-commander.py --models

# 测试知识库
python3 ~/.claude/skills/local-commander/local-commander.py --kb-stats
```

---

## 使用方法

### Skill 模式 (交互式)

```bash
# 激活
/local

# 执行任务
/local 写一个 Kotlin 扩展函数
/local --model 27b 设计支付架构
/local --image ~/Downloads/screenshot.png 分析这个UI

# 知识库操作
/local --kb-add "在 Swift 中使用 @escaping 标记异步闭包"
/local --kb-search "闭包 异步"
/local --kb-list
```

### MCP 模式 (程序化调用)

```python
# 执行本地任务
mcp__local-commander-router__execute_local({
    "task": "写一个 TypeScript 函数",
    "model": "coder"  # 可选，自动路由
})

# 代码审查工作流
mcp__local-commander-router__generate_with_review({
    "task": "实现用户登录验证",
    "language": "TypeScript"
})

# 知识库操作
mcp__local-commander-router__kb_add({
    "text": "知识点内容",
    "category": "coding",
    "tags": ["python", "async"]
})

mcp__local-commander-router__kb_search({
    "query": "RAG 向量搜索",
    "top_k": 5
})
```

---

## 🔄 代码审查工作流

完整的代码生成 → 审查 → 修复闭环，实现自动化代码质量保证。

### 工作原理

```
┌────────────────────────────────────────────────────────────────┐
│                    generate_with_review                         │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐                  │
│   │ coder   │────▶│   27b   │────▶│  coder  │──┐               │
│   │ 生成代码 │     │ 审查代码 │     │ 修复问题 │  │               │
│   └─────────┘     └─────────┘     └─────────┘  │               │
│        │               │               ▲       │               │
│        │               ▼               │       │               │
│        │         ┌───────────┐         │       │               │
│        │         │ 有问题？  │─────────┘       │               │
│        │         └───────────┘                 │               │
│        │               │                       │               │
│        │               ▼ 无问题                │               │
│        │         ┌───────────┐                 │               │
│        └────────▶│ 返回结果  │◀────────────────┘               │
│                  └───────────┘   (最多迭代 2 次)                │
└────────────────────────────────────────────────────────────────┘
```

### 模型分工与原因

| 模型 | 职责 | 原因 |
|------|------|------|
| `coder` (14B) | 代码生成、修复 | 专注代码领域，生成质量高 |
| `27b` | 代码审查、问题分析 | 参数量大，推理能力强，能发现深层问题 |

**为什么用两个模型？**

- **专业性**: coder 专注代码生成，对语法和模式更熟悉
- **客观性**: 27b 作为独立审查者，不受生成者偏见影响
- **互补性**: 生成者可能忽略的问题，审查者能发现

### 详细流程

```
Step 1: coder 生成代码
────────────────────────
输入: "实现用户登录验证"
输出: 原始代码 v1
        │
        ▼
Step 2: 27b 审查代码
────────────────────────
审查维度:
  ├─ 代码质量: 可读性、命名规范、代码风格
  ├─ 安全性: 输入验证、注入风险、敏感数据处理
  ├─ 性能: 算法复杂度、内存使用
  └─ 最佳实践: 设计模式、错误处理
输出: 审查报告
        │
        ▼
Step 3: 判断是否需要修复
────────────────────────
检查报告是否包含:
  - "代码质量良好"
  - "无需修改"
  - "没有发现"

┌───────┴───────┐
│               │
▼ 是            ▼ 否
返回结果      Step 4: coder 修复代码
             ────────────────────────
             输入:
               - 原始代码
               - 审查报告中的问题
             输出: 修复后的代码 v2
                    │
                    ▼
             回到 Step 2 (最多 2 次)
```

### 审查报告格式

```
1. 【评分】整体质量评分 (1-10)
2. 【问题】发现的问题列表（按严重程度排序）
   - 🔴 严重: SQL 注入风险
   - 🟡 中等: 变量命名不规范
   - 🟢 轻微: 缺少注释
3. 【建议】改进建议
4. 【优点】代码的优点
```

### MCP 调用

```python
# 完整工作流：生成 → 审查 → 修复
mcp__local-commander-router__generate_with_review({
    "task": "实现用户登录验证",
    "language": "TypeScript",
    "max_fix_iterations": 2  # 最大修复迭代次数
})

# 返回结果示例
{
    "success": true,
    "final_code": "...修复后的代码...",
    "review_reports": [
        {"iteration": 1, "report": "发现问题: ..."},
        {"iteration": 2, "report": "代码质量良好，无需修改"}
    ],
    "iterations": [
        {"step": "generate", "success": true},
        {"step": "review", "iteration": 1, "needs_fix": true},
        {"step": "fix", "iteration": 1, "success": true},
        {"step": "review", "iteration": 2, "needs_fix": false}
    ]
}

# 单独审查代码
mcp__local-commander-router__review_code({
    "code": "... 你的代码 ...",
    "language": "TypeScript",
    "focus": "all"  # quality / security / performance / all
})

# 单独修复问题
mcp__local-commander-router__fix_code({
    "code": "... 原始代码 ...",
    "issues": "... 审查报告中的问题 ...",
    "language": "TypeScript"
})
```

### 审查重点选项

| focus | 审查重点 |
|-------|---------|
| `quality` | 可读性、可维护性、代码风格、命名规范 |
| `security` | 输入验证、注入风险、敏感数据处理、权限控制 |
| `performance` | 算法复杂度、内存使用、数据库查询优化 |
| `all` | 全面审查：代码质量、安全性、性能、最佳实践 |

### 优势

| 优势 | 说明 |
|------|------|
| 🎯 **自动化** | 无需人工干预，自动完成生成-审查-修复循环 |
| 🔒 **质量保证** | 多轮审查确保代码质量 |
| 💰 **成本优化** | 本地模型执行，无需调用云端 API |
| 📊 **可追溯** | 返回完整的迭代记录和审查报告 |

---

## 🧪 UI 自动化验收测试

前端开发闭环：写代码 → 自动截图 → VL 分析 → 发现问题 → 自动修复。

### MCP 调用

```python
# 单页面分析
mcp__local-commander-router__ui_analyze_page({
    "url": "http://localhost:3000/tasks",
    "analysis_prompt": "分析这个页面的功能和问题"
})

# 批量页面测试
mcp__local-commander-router__ui_test_pages({
    "base_url": "http://localhost:3000",
    "pages": ["/", "/tasks", "/settings"],
    "page_names": ["首页", "任务管理", "设置"]
})

# 仅截图
mcp__local-commander-router__ui_screenshot({
    "url": "http://localhost:3000",
    "output_path": "/tmp/screenshot.png"
})

# 交互测试
mcp__local-commander-router__ui_click_and_verify({
    "url": "http://localhost:3000/tasks",
    "selector": "button.new-task",
    "verify_type": "screenshot",  # 或 "text", "element"
    "verify_target": "弹窗是否出现"
})
```

### 技术原理

```
Playwright (浏览器自动化) → 截图 → VL 视觉模型 (图像理解) → 分析报告
```

### 使用场景

- 前端页面开发完成后自动验收
- 检测 UI 是否正常渲染
- 发现功能问题和 UI 缺陷
- 批量测试多个页面

---

## 🧪 自动化测试 (Android/iOS/Web)

支持全平台自动化测试，可与代码生成流程集成。

### CLI 调用

```bash
# 自动检测项目类型并运行测试
/local --test

# 指定测试类型
/local --test --test-type espresso   # Android Espresso
/local --test --test-type xctest     # iOS XCTest
/local --test --test-type playwright # Web Playwright

# 指定设备和目标
/local --test --test-device "emulator-5554"
/local --test --test-target "com.example.app"

# 智能模式 + 测试 (生成代码后自动测试)
/local --smart --test "帮我改进登录页面"
```

### 支持的测试框架

| 平台 | 测试框架 |
|------|---------|
| Android | Espresso, UI Automator, Appium |
| iOS | XCTest, XCUITest |
| Web | Playwright, Selenium |

---

## 📱 Android UI 自动化测试 (ADB 方案)

**无需 Appium，直接使用 ADB 实现 Android UI 自动化！**

### 技术原理

```
ADB Shell 命令 → UI Automator Dump → XML 解析 → 元素定位 → 操作执行 → VL 视觉验证
```

**核心优势：**
- 🚀 **零依赖**: 无需 Appium Server，只需 ADB
- 🎯 **精准定位**: 通过 text、resource_id、content_desc、class 定位元素
- 📸 **视觉验证**: 结合 VL 模型分析截图，验证 UI 状态
- 🔄 **测试序列**: 支持复杂的多步骤测试流程

### 实现架构

```
┌─────────────────────────────────────────────────────────────┐
│                    AndroidUIAutomation                       │
├─────────────────────────────────────────────────────────────┤
│  基础操作层                                                  │
│  ├── tap(x, y)          # 点击坐标                          │
│  ├── swipe(x1,y1,x2,y2) # 滑动                              │
│  ├── input_text(text)   # 输入文本                          │
│  ├── press_key(keycode) # 按键事件                          │
│  └── screenshot()       # 截图                              │
├─────────────────────────────────────────────────────────────┤
│  元素定位层                                                  │
│  ├── dump_ui()          # 获取 UI 层级 XML                  │
│  ├── find_element()     # 查找单个元素                      │
│  ├── find_elements()    # 查找多个元素                      │
│  └── get_element_center() # 获取元素中心坐标                │
├─────────────────────────────────────────────────────────────┤
│  高级操作层                                                  │
│  ├── tap_element()      # 通过属性定位并点击                │
│  ├── start_app()        # 启动应用                          │
│  ├── force_stop()       # 强制停止应用                      │
│  └── run_test_sequence() # 运行测试序列                     │
└─────────────────────────────────────────────────────────────┘
```

### MCP 工具调用

```python
# 获取 UI 元素列表
mcp__local-commander-router__android_dump_ui({})

# 点击元素 (通过属性定位)
mcp__local-commander-router__android_tap({
    "text": "登录",           # 可选: 通过文本定位
    "resource_id": "btn_login", # 可选: 通过 resource-id 定位
    "content_desc": "登录按钮"  # 可选: 通过 content-desc 定位
})

# 截图
mcp__local-commander-router__android_screenshot({
    "save_path": "/tmp/test.png"  # 可选，默认临时目录
})

# 运行测试序列
mcp__local-commander-router__android_run_test({
    "steps": [
        {"action": "tap", "element": {"text": "设置"}},
        {"action": "screenshot"},
        {"action": "swipe", "x1": 540, "y1": 1500, "x2": 540, "y2": 800},
        {"action": "tap", "element": {"text": "English"}},
        {"action": "tap", "element": {"resource_id": "btn_save"}},
        {"action": "assert_element", "element": {"text": "New Chat"}},
        {"action": "back"},
        {"action": "wait", "seconds": 2}
    ]
})
```

### Python 直接使用

```python
from android_ui_automation import AndroidUIAutomation

# 初始化 (自动检测设备)
auto = AndroidUIAutomation()

# 获取 UI 元素
ui = auto.dump_ui()
print(f"元素数量: {ui['element_count']}")

# 通过文本点击
auto.tap_element(text="登录")

# 通过 resource_id 点击
auto.tap_element(resource_id="com.example.app:id/btn_submit")

# 通过 content_desc 点击
auto.tap_element(content_desc="返回按钮")

# 截图
path = auto.screenshot("/tmp/screen.png")

# 滑动
auto.swipe(540, 1500, 540, 800)  # 向上滑动

# 输入文本 (需先点击输入框)
auto.tap_element(resource_id="input_field")
auto.input_text("Hello World")

# 按键
auto.back()  # 返回
auto.home()  # 回到桌面

# 运行测试序列
result = auto.run_test_sequence([
    {"action": "tap", "element": {"text": "设置"}},
    {"action": "screenshot"},
    {"action": "back"}
])
print(f"通过: {result['passed']}/{result['total']}")
```

### 支持的操作

| 操作 | 参数 | 说明 |
|------|------|------|
| `tap` | `element` | 点击元素 (通过属性定位) |
| `tap_coords` | `x`, `y` | 点击坐标 |
| `input` | `text` | 输入文本 |
| `swipe` | `x1`, `y1`, `x2`, `y2`, `duration` | 滑动 |
| `back` | - | 返回键 |
| `home` | - | Home 键 |
| `screenshot` | `save_path` | 截图 |
| `wait` | `seconds` | 等待 |
| `assert_element` | `element` | 断言元素存在 |
| `start_app` | `package`, `activity` | 启动应用 |

### 元素定位方式

```python
# 1. 通过文本 (部分匹配)
auto.tap_element(text="登录")

# 2. 通过 resource-id (部分匹配)
auto.tap_element(resource_id="btn_login")

# 3. 通过 content-desc (部分匹配)
auto.tap_element(content_desc="登录按钮")

# 4. 通过 class (部分匹配)
auto.tap_element(class_name="android.widget.Button")

# 5. 组合定位
auto.tap_element(text="登录", class_name="Button")
```

### 与 VL 模型结合

```python
# 截图 + VL 分析
from android_ui_automation import AndroidUIAutomation

auto = AndroidUIAutomation()

# 执行操作
auto.tap_element(text="设置")
auto.screenshot("/tmp/settings.png")

# 使用 VL 模型分析
# mcp__local-commander-router__execute_local({
#     "model": "vl",
#     "image_path": "/tmp/settings.png",
#     "task": "分析设置页面，检查是否有语言选项"
# })
```

### 系统要求

- **ADB**: Android Debug Bridge (Android SDK)
- **设备**: 已开启 USB 调试的 Android 设备或模拟器
- **Python**: 3.10+

### 调试技巧

```bash
# 检查设备连接
adb devices

# 手动获取 UI 层级
adb shell uiautomator dump /sdcard/ui.xml
adb pull /sdcard/ui.xml

# 手动截图
adb shell screencap -p /sdcard/screen.png
adb pull /sdcard/screen.png

# 查看当前 Activity
adb shell dumpsys activity activities | grep mResumedActivity
```

---

## 项目结构

```
~/.claude/skills/local-commander/
├── SKILL.md                    # Skill 定义 (Claude Code 自动加载)
├── README.md                   # 本文档
├── local-commander.py          # CLI 入口
├── lib/
│   ├── mcp_router.py           # MCP 服务入口
│   ├── router.py               # 模型路由
│   ├── executor.py             # 任务执行器
│   ├── embedder.py             # BGE-M3 向量化
│   ├── knowledge_base_chroma.py # ChromaDB 知识库
│   ├── android_ui_automation.py # Android UI 自动化 (ADB 方案)
│   └── testers/                # 自动化测试器
│       ├── android_tester.py
│       ├── ios_tester.py
│       └── web_tester.py
└── config/
    └── models.json             # 模型配置
```

---

## 数据存储位置

| 数据 | 位置 | 说明 |
|------|------|------|
| MLX 模型 | `~/.cache/huggingface/hub/models--mlx-community--*/` | 4-bit 量化模型 |
| Embedding 模型 | `~/.cache/huggingface/hub/models--BAAI--bge-m3/` | BGE-M3 向量模型 |
| 知识库 | `~/.claude/knowledge_chroma/` | ChromaDB 向量数据库 |
| 会话数据 | `~/.local-commander/` | 历史记录 |

---

## 依赖清单

### Python 包

```
mlx>=0.20.0
mlx-lm>=0.19.0
mlx-vlm>=0.1.0
sentence-transformers>=2.2.0
chromadb>=0.4.0
numpy>=1.24.0
torch>=2.0.0
```

### Node.js 包 (可选)

```
playwright>=1.40.0
```

### 系统依赖

- HuggingFace CLI (`pip install huggingface_hub`)
- Git LFS (用于下载大模型)

---

## 常见问题

### 1. 模型下载慢？

```bash
# 使用镜像站
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download Qwen/Qwen2.5-Coder-14B-Instruct ...
```

### 2. 内存不足？

- 使用量化模型 (4-bit)
- 减少并发模型数
- 只下载需要的模型

### 3. ChromaDB 报错？

```bash
# 重新安装
pip3 install --break-system-packages --upgrade chromadb
```

### 4. MPS 不可用？

确保 macOS 版本 >= 12.3，且使用 Apple Silicon Mac。

---

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 PR！
