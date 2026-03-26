#!/usr/bin/env python3
"""
Local Commander MCP Router Service
MCP 标准协议服务器 - 自动识别任务类型并路由到合适的本地模型
"""

import json
import sys
import asyncio
import subprocess
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class ModelType(Enum):
    CODER = "coder"       # Qwen2.5-Coder-14B - 代码生成、审查、Debug
    VL = "vl"             # Qwen2.5-VL-7B - 图像分析、UI验证、OCR
    REASONING = "27b"     # Qwen3.5-27B - 复杂推理、架构设计
    FAST = "7b"           # Qwen2.5-7B - 轻量对话、快速回答
    CLOUD = "cloud"       # 使用云端模型


@dataclass
class TaskClassification:
    task_type: str
    model: str
    confidence: float
    reason: str


class TaskClassifier:
    """任务分类器 - 分析任务类型并选择合适的模型"""

    # 关键词映射
    KEYWORDS = {
        ModelType.CODER: [
            "代码", "编程", "Kotlin", "Swift", "函数", "类", "实现",
            "写", "生成", "bug", "debug", "修复", "重构",
            "代码审查", "优化", "算法", "code", "implement",
            "function", "class", "method", "variable"
        ],
        ModelType.VL: [
            "图片", "截图", "图像", "UI", "界面", "分析图", "看",
            "截图分析", "OCR", "识别", "视觉", "image", "screenshot",
            "UI设计", "界面设计", "图表分析"
        ],
        ModelType.REASONING: [
            "架构", "设计", "方案", "分析", "评估", "解释",
            "为什么", "怎么", "如何", "比较", "优劣",
            "architecture", "design", "explain", "analyze"
        ],
        ModelType.FAST: [
            "你好", "hello", "hi", "谢谢", "快速", "简单",
            "是什么", "怎么用", "简介", "概述"
        ]
    }

    def classify(self, task: str, has_image: bool = False) -> TaskClassification:
        """分析任务并返回分类结果"""
        task_lower = task.lower()

        # 1. 如果有图片，直接路由到 VL 模型
        if has_image:
            return TaskClassification(
                task_type="image_analysis",
                model=ModelType.VL.value,
                confidence=1.0,
                reason="检测到图片输入，使用 VL 模型"
            )

        # 2. 计算各类型的匹配分数
        scores = {}
        for model_type, keywords in self.KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in task_lower)
            scores[model_type] = score

        # 3. 选择最高分的类型
        best_model = max(scores, key=scores.get)
        best_score = scores[best_model]
        total_score = sum(scores.values())

        # 4. 计算置信度
        if total_score == 0:
            return TaskClassification(
                task_type="general",
                model=ModelType.CLOUD.value,
                confidence=0.5,
                reason="未检测到特定类型关键词，建议使用云端模型"
            )

        confidence = best_score / total_score if total_score > 0 else 0

        # 5. 确定任务类型名称
        task_types = {
            ModelType.CODER: "code_generation",
            ModelType.VL: "image_analysis",
            ModelType.REASONING: "complex_reasoning",
            ModelType.FAST: "quick_qa"
        }

        return TaskClassification(
            task_type=task_types.get(best_model, "general"),
            model=best_model.value,
            confidence=confidence,
            reason=f"检测到 {best_score} 个 {best_model.value} 相关关键词"
        )


class MCPRouterServer:
    """MCP 路由服务器 - 实现 MCP 标准协议"""

    def __init__(self):
        self.classifier = TaskClassifier()
        self.server_info = {
            "name": "local-commander-router",
            "version": "2.1.0"  # 新增 UI 自动化验收测试
        }
        self.tools = [
            {
                "name": "classify_task",
                "description": "分析任务类型并推荐合适的本地模型。输入任务描述，返回推荐的模型类型和置信度。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "任务描述文本"
                        },
                        "has_image": {
                            "type": "boolean",
                            "description": "是否包含图片输入",
                            "default": False
                        }
                    },
                    "required": ["task"]
                }
            },
            {
                "name": "route_task",
                "description": "路由任务到合适的本地模型并返回执行命令。自动分析任务类型并构建调用参数。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "任务描述文本"
                        },
                        "has_image": {
                            "type": "boolean",
                            "description": "是否包含图片输入",
                            "default": False
                        },
                        "smart": {
                            "type": "boolean",
                            "description": "启用智能模式（自动代码生成）",
                            "default": False
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "最大输出 token 数",
                            "default": 4096
                        }
                    },
                    "required": ["task"]
                }
            },
            {
                "name": "execute_local",
                "description": "在本地模型上执行任务。调用本地 MLX 模型处理代码生成、图像分析等任务，可节省 90%+ Token。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "任务描述文本"
                        },
                        "model": {
                            "type": "string",
                            "enum": ["coder", "vl", "27b", "7b"],
                            "description": "指定模型类型: coder(代码), vl(图像), 27b(推理), 7b(快速)"
                        },
                        "has_image": {
                            "type": "boolean",
                            "description": "是否包含图片输入",
                            "default": False
                        },
                        "image_path": {
                            "type": "string",
                            "description": "图片路径（仅 vl 模型需要）"
                        },
                        "smart": {
                            "type": "boolean",
                            "description": "启用智能模式",
                            "default": False
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "最大输出 token 数",
                            "default": 4096
                        }
                    },
                    "required": ["task"]
                }
            },
            # ========== 新增工具 ==========
            {
                "name": "review_code",
                "description": "使用 27b 推理模型审查代码。检查代码质量、安全性、最佳实践，返回审查报告和改进建议。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要审查的代码内容"
                        },
                        "language": {
                            "type": "string",
                            "description": "代码语言，如 TypeScript, Python, Kotlin 等",
                            "default": "auto"
                        },
                        "focus": {
                            "type": "string",
                            "description": "审查重点：quality(质量), security(安全), performance(性能), all(全部)",
                            "enum": ["quality", "security", "performance", "all"],
                            "default": "all"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "generate_with_review",
                "description": "完整的代码生成工作流：生成代码 → 审查代码 → 自动修复问题。返回最终代码和审查报告。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "代码生成任务描述"
                        },
                        "language": {
                            "type": "string",
                            "description": "目标编程语言",
                            "default": "TypeScript"
                        },
                        "max_fix_iterations": {
                            "type": "integer",
                            "description": "最大修复迭代次数",
                            "default": 2
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "最大输出 token 数",
                            "default": 8192
                        }
                    },
                    "required": ["task"]
                }
            },
            {
                "name": "fix_code",
                "description": "使用 coder 模型修复代码问题。输入代码和问题描述，返回修复后的代码。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "原始代码"
                        },
                        "issues": {
                            "type": "string",
                            "description": "需要修复的问题描述（来自审查报告）"
                        },
                        "language": {
                            "type": "string",
                            "description": "代码语言",
                            "default": "auto"
                        }
                    },
                    "required": ["code", "issues"]
                }
            },
            # ========== UI 自动化测试工具 ==========
            {
                "name": "ui_screenshot",
                "description": "使用 Playwright 截取网页截图。输入 URL，返回截图文件路径。用于前端 UI 自动化验收。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "要截取的网页 URL（如 http://localhost:3000）"
                        },
                        "output_path": {
                            "type": "string",
                            "description": "截图保存路径（默认 /tmp/ui-screenshot.png）"
                        },
                        "viewport_width": {
                            "type": "integer",
                            "description": "视口宽度",
                            "default": 1400
                        },
                        "viewport_height": {
                            "type": "integer",
                            "description": "视口高度",
                            "default": 900
                        },
                        "wait_time": {
                            "type": "integer",
                            "description": "等待页面加载时间（毫秒）",
                            "default": 2000
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "ui_analyze_page",
                "description": "截取网页截图并用 VL 视觉模型分析。自动截图+分析，返回页面功能、布局、问题描述。用于前端自动化验收测试。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "要分析的网页 URL"
                        },
                        "analysis_prompt": {
                            "type": "string",
                            "description": "分析提示词（默认分析页面功能、布局、问题）",
                            "default": "分析这个页面的功能、布局、UI设计，指出问题和改进建议"
                        },
                        "viewport_width": {
                            "type": "integer",
                            "default": 1400
                        },
                        "viewport_height": {
                            "type": "integer",
                            "default": 900
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "ui_test_pages",
                "description": "批量测试多个页面。输入页面 URL 列表，自动截图并分析每个页面，返回测试报告。用于前端应用完整验收。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base_url": {
                            "type": "string",
                            "description": "基础 URL（如 http://localhost:3000）"
                        },
                        "pages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "页面路径列表（如 ['/tasks', '/logs', '/settings']）"
                        },
                        "page_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "页面名称列表（可选，用于报告）"
                        }
                    },
                    "required": ["base_url", "pages"]
                }
            },
            {
                "name": "ui_click_and_verify",
                "description": "点击页面元素并验证结果。用于交互测试，如点击按钮后验证页面变化或弹窗。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "页面 URL"
                        },
                        "selector": {
                            "type": "string",
                            "description": "要点击的元素选择器（CSS 选择器）"
                        },
                        "verify_type": {
                            "type": "string",
                            "enum": ["screenshot", "text", "element"],
                            "description": "验证方式：screenshot(截图分析), text(文本内容), element(元素存在)"
                        },
                        "verify_target": {
                            "type": "string",
                            "description": "验证目标：截图分析提示词/期望文本/元素选择器"
                        }
                    },
                    "required": ["url", "selector", "verify_type"]
                }
            },
            # ========== 增强版 UI 测试工具 ==========
            {
                "name": "ui_test_spa",
                "description": "SPA 应用路由测试。通过点击菜单导航测试不同页面，支持前端路由。适用于 React/Vue/Tauri 等单页应用。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "应用入口 URL（如 http://localhost:1420）"
                        },
                        "routes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "路由名称"},
                                    "menu_text": {"type": "string", "description": "菜单文本（用于点击定位）"},
                                    "expected_elements": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "期望出现的元素文本列表"
                                    }
                                }
                            },
                            "description": "路由配置列表"
                        },
                        "viewport_width": {"type": "integer", "default": 1200},
                        "viewport_height": {"type": "integer", "default": 800}
                    },
                    "required": ["url", "routes"]
                }
            },
            {
                "name": "ui_interact",
                "description": "高级交互测试。支持表单填写、点击、键盘操作、拖拽等复杂交互，并可验证结果。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "页面 URL"},
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "enum": ["click", "fill", "select", "press", "wait", "screenshot", "assert_text", "assert_element"],
                                        "description": "操作类型"
                                    },
                                    "selector": {"type": "string", "description": "CSS 选择器或文本选择器"},
                                    "value": {"type": "string", "description": "输入值或按键"},
                                    "timeout": {"type": "integer", "description": "超时时间（毫秒）"}
                                }
                            },
                            "description": "交互步骤列表"
                        },
                        "screenshot_on_complete": {
                            "type": "boolean",
                            "default": True,
                            "description": "完成后是否截图"
                        }
                    },
                    "required": ["url", "steps"]
                }
            },
            {
                "name": "ui_desktop_app",
                "description": "桌面应用测试（Tauri/Electron）。自动检测本地端口服务状态，等待应用启动后进行测试。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "port": {"type": "integer", "description": "应用端口（默认自动检测）"},
                        "wait_for_ready": {"type": "boolean", "default": True, "description": "等待服务就绪"},
                        "timeout": {"type": "integer", "default": 30000, "description": "等待超时（毫秒）"},
                        "test_routes": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "路由测试配置（同 ui_test_spa）"
                        }
                    }
                }
            },
            {
                "name": "ui_generate_report",
                "description": "生成 HTML 测试报告。将测试结果汇总为可视化报告，包含截图和分析。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "报告标题"},
                        "output_path": {"type": "string", "default": "/tmp/ui-test-report.html"},
                        "test_results": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "测试结果列表"
                        }
                    },
                    "required": ["test_results"]
                }
            },
            # ========== 原生窗口测试工具 ==========
            {
                "name": "native_window_list",
                "description": "列出 macOS 原生应用窗口。获取当前运行的应用及其窗口信息，用于原生窗口自动化测试。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "应用名称过滤（可选，如 'Safari', 'Finder'）"
                        }
                    }
                }
            },
            {
                "name": "native_window_elements",
                "description": "获取原生窗口的 UI 元素树。用于定位按钮、文本框等可交互元素。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "应用名称"
                        },
                        "window_title": {
                            "type": "string",
                            "description": "窗口标题（可选）"
                        }
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "native_window_action",
                "description": "对原生窗口执行操作。支持点击、输入、获取文本等操作。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "应用名称"},
                        "action": {
                            "type": "string",
                            "enum": ["click", "input", "get_text", "press_key", "screenshot"],
                            "description": "操作类型"
                        },
                        "element": {
                            "type": "string",
                            "description": "元素标识（文本内容或 AXRole）"
                        },
                        "value": {
                            "type": "string",
                            "description": "输入值或按键（input/press_key 时使用）"
                        }
                    },
                    "required": ["app_name", "action"]
                }
            },
            # ========== API 测试工具 ==========
            {
                "name": "api_request",
                "description": "发送 HTTP API 请求。支持 GET/POST/PUT/DELETE，可断言状态码和响应体。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                            "default": "GET"
                        },
                        "url": {"type": "string", "description": "请求 URL"},
                        "headers": {
                            "type": "object",
                            "description": "请求头"
                        },
                        "body": {
                            "type": "object",
                            "description": "请求体（JSON）"
                        },
                        "timeout": {
                            "type": "integer",
                            "default": 30,
                            "description": "超时时间（秒）"
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "api_test_sequence",
                "description": "批量 API 测试。执行多个 API 请求并验证响应，生成测试报告。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "description": "基础 URL"},
                        "tests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "测试名称"},
                                    "method": {"type": "string"},
                                    "path": {"type": "string", "description": "API 路径"},
                                    "expected_status": {"type": "integer", "default": 200},
                                    "expected_fields": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "期望响应字段"
                                    }
                                }
                            },
                            "description": "测试用例列表"
                        },
                        "auth_token": {"type": "string", "description": "认证 Token（可选）"}
                    },
                    "required": ["base_url", "tests"]
                }
            },
            # ========== iOS 模拟器测试工具 ==========
            {
                "name": "ios_simulator_list",
                "description": "列出可用的 iOS 模拟器。返回模拟器名称、UDID、状态和系统版本。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["all", "booted", "shutdown"],
                            "default": "all",
                            "description": "筛选状态：all(全部), booted(已启动), shutdown(已关闭)"
                        }
                    }
                }
            },
            {
                "name": "ios_simulator_control",
                "description": "控制 iOS 模拟器。支持启动、关闭、重启模拟器。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["boot", "shutdown", "restart", "erase"],
                            "description": "操作：boot(启动), shutdown(关闭), restart(重启), erase(重置)"
                        },
                        "device": {
                            "type": "string",
                            "description": "设备名称或 UDID（如 'iPhone 16 Pro' 或 UDID）"
                        }
                    },
                    "required": ["action", "device"]
                }
            },
            {
                "name": "ios_simulator_screenshot",
                "description": "截取 iOS 模拟器屏幕。返回截图文件路径。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device": {
                            "type": "string",
                            "description": "设备 UDID（可选，默认使用已启动的设备）"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/tmp/ios-screenshot.png",
                            "description": "截图保存路径"
                        }
                    }
                }
            },
            {
                "name": "ios_simulator_action",
                "description": "在 iOS 模拟器上执行操作。支持点击、输入、按键、滑动等。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["tap", "input", "press_key", "swipe", "home", "siri"],
                            "description": "操作类型"
                        },
                        "x": {"type": "integer", "description": "X 坐标 (tap/swipe)"},
                        "y": {"type": "integer", "description": "Y 坐标 (tap/swipe)"},
                        "end_x": {"type": "integer", "description": "结束 X 坐标 (swipe)"},
                        "end_y": {"type": "integer", "description": "结束 Y 坐标 (swipe)"},
                        "text": {"type": "string", "description": "输入文本 (input)"},
                        "key": {"type": "string", "description": "按键名称 (press_key)"},
                        "device": {"type": "string", "description": "设备 UDID（可选）"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "ios_simulator_app",
                "description": "管理 iOS 模拟器中的应用。支持安装、启动、卸载应用。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["install", "launch", "terminate", "uninstall", "list"],
                            "description": "操作类型"
                        },
                        "app_path": {
                            "type": "string",
                            "description": "应用路径 (.app 或 .ipa) - install 时使用"
                        },
                        "bundle_id": {
                            "type": "string",
                            "description": "应用 Bundle ID - launch/terminate/uninstall 时使用"
                        },
                        "device": {"type": "string", "description": "设备 UDID（可选）"}
                    },
                    "required": ["action"]
                }
            },
            # ========== iOS 真机测试工具 ==========
            {
                "name": "ios_device_list",
                "description": "列出连接的 iOS 真机设备。需要安装 libimobiledevice。",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "ios_device_screenshot",
                "description": "截取 iOS 真机屏幕。需要 USB 连接和信任此电脑。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "udid": {
                            "type": "string",
                            "description": "设备 UDID（可选，默认使用第一个设备）"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/tmp/ios-device-screenshot.png"
                        }
                    }
                }
            },
            # ========== AI 知识库工具 ==========
            {
                "name": "kb_add",
                "description": "添加知识点到 AI 知识库。用于存储学习到的新知识、最佳实践、解决方案等。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "知识点内容"
                        },
                        "category": {
                            "type": "string",
                            "description": "分类：coding, architecture, debugging, tools, concepts, general",
                            "default": "general"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "标签列表，如 ['python', 'async', '最佳实践']"
                        },
                        "importance": {
                            "type": "number",
                            "description": "重要程度 0-1",
                            "default": 0.5
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "kb_search",
                "description": "搜索知识库。使用语义相似度查找相关知识点。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回结果数量",
                            "default": 5
                        },
                        "category": {
                            "type": "string",
                            "description": "限定分类"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "限定标签（需全部匹配）"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "kb_list",
                "description": "列出知识库中的知识点。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "限定分类"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "限定标签"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回数量限制",
                            "default": 20
                        }
                    }
                }
            },
            {
                "name": "kb_stats",
                "description": "获取知识库统计信息。",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "kb_delete",
                "description": "删除知识点。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "知识点 ID"
                        }
                    },
                    "required": ["id"]
                }
            },
            # ========== Android UI 自动化工具 ==========
            {
                "name": "android_dump_ui",
                "description": "获取 Android 设备当前界面的 UI 元素列表。返回可点击的元素及其属性。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device_serial": {
                            "type": "string",
                            "description": "设备序列号（可选，默认使用第一个连接的设备）"
                        }
                    }
                }
            },
            {
                "name": "android_tap",
                "description": "点击 Android 设备上的 UI 元素。可通过文本、resource_id 或 content_desc 定位。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "元素文本内容"
                        },
                        "resource_id": {
                            "type": "string",
                            "description": "元素 resource-id"
                        },
                        "content_desc": {
                            "type": "string",
                            "description": "元素 content-description"
                        },
                        "x": {
                            "type": "integer",
                            "description": "直接点击坐标 X（与其他参数互斥）"
                        },
                        "y": {
                            "type": "integer",
                            "description": "直接点击坐标 Y（与其他参数互斥）"
                        }
                    }
                }
            },
            {
                "name": "android_screenshot",
                "description": "截取 Android 设备当前屏幕。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "save_path": {
                            "type": "string",
                            "description": "截图保存路径（默认 /tmp/android_screenshot.png）"
                        }
                    }
                }
            },
            {
                "name": "android_run_test",
                "description": "在 Android 设备上运行 UI 自动化测试序列。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "description": "测试步骤列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "description": "操作类型: tap, input, back, screenshot, wait, assert_element"
                                    }
                                }
                            }
                        }
                    },
                    "required": ["steps"]
                }
            }
        ]

    async def handle_request(self, request: dict) -> dict:
        """处理 MCP 请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        # 标准 MCP 方法
        if method == "initialize":
            return self._response(request_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": self.server_info
            })

        elif method == "notifications/initialized":
            # 通知，无需响应
            return None

        elif method == "tools/list":
            return self._response(request_id, {
                "tools": self.tools
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            return await self._call_tool(request_id, tool_name, tool_args)

        else:
            return self._error(request_id, f"Unknown method: {method}")

    def _response(self, request_id: Any, result: Any) -> dict:
        """构建成功响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }

    def _error(self, request_id: Any, message: str, code: int = -32600) -> dict:
        """构建错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }

    async def _call_tool(self, request_id: Any, tool_name: str, args: dict) -> dict:
        """执行工具调用"""
        try:
            if tool_name == "classify_task":
                result = self._classify_task(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(asdict(result), ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "route_task":
                result = self._route_task(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "execute_local":
                result = await self._execute_local(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== 新增工具实现 ==========
            elif tool_name == "review_code":
                result = await self._review_code(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "generate_with_review":
                result = await self._generate_with_review(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "fix_code":
                result = await self._fix_code(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== 新增工具实现 ==========

            # ========== UI 自动化测试工具 ==========
            elif tool_name == "ui_screenshot":
                result = await self._ui_screenshot(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "ui_analyze_page":
                result = await self._ui_analyze_page(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "ui_test_pages":
                result = await self._ui_test_pages(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "ui_click_and_verify":
                result = await self._ui_click_and_verify(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== 增强版 UI 测试工具实现 ==========
            elif tool_name == "ui_test_spa":
                result = await self._ui_test_spa(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ui_interact":
                result = await self._ui_interact(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ui_desktop_app":
                result = await self._ui_desktop_app(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ui_generate_report":
                result = self._ui_generate_report(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== 原生窗口测试工具实现 ==========
            elif tool_name == "native_window_list":
                result = self._native_window_list(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "native_window_elements":
                result = self._native_window_elements(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "native_window_action":
                result = self._native_window_action(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== API 测试工具实现 ==========
            elif tool_name == "api_request":
                result = await self._api_request(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "api_test_sequence":
                result = await self._api_test_sequence(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== iOS 模拟器测试工具实现 ==========
            elif tool_name == "ios_simulator_list":
                result = self._ios_simulator_list(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ios_simulator_control":
                result = self._ios_simulator_control(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ios_simulator_screenshot":
                result = self._ios_simulator_screenshot(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ios_simulator_action":
                result = self._ios_simulator_action(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ios_simulator_app":
                result = self._ios_simulator_app(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== iOS 真机测试工具实现 ==========
            elif tool_name == "ios_device_list":
                result = self._ios_device_list(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })
            elif tool_name == "ios_device_screenshot":
                result = self._ios_device_screenshot(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== AI 知识库工具实现 ==========
            elif tool_name == "kb_add":
                result = self._kb_add(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "kb_search":
                result = self._kb_search(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "kb_list":
                result = self._kb_list(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "kb_stats":
                result = self._kb_stats()
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "kb_delete":
                result = self._kb_delete(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            # ========== Android UI 自动化工具实现 ==========
            elif tool_name == "android_dump_ui":
                result = self._android_dump_ui(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "android_tap":
                result = self._android_tap(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "android_screenshot":
                result = self._android_screenshot(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            elif tool_name == "android_run_test":
                result = self._android_run_test(args)
                return self._response(request_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                })

            else:
                return self._error(request_id, f"Unknown tool: {tool_name}")

        except Exception as e:
            return self._error(request_id, f"Tool execution error: {str(e)}")

    def _classify_task(self, args: dict) -> TaskClassification:
        """分类任务"""
        task = args.get("task", "")
        has_image = args.get("has_image", False)
        return self.classifier.classify(task, has_image)

    def _route_task(self, args: dict) -> dict:
        """路由任务"""
        task = args.get("task", "")
        has_image = args.get("has_image", False)

        result = self.classifier.classify(task, has_image)

        return {
            "should_use_local": result.model != "cloud",
            "recommended_model": result.model,
            "command": self._build_command(result.model, task, args),
            "classification": asdict(result)
        }

    async def _execute_local(self, args: dict) -> dict:
        """执行本地任务"""
        task = args.get("task", "")
        model = args.get("model")
        has_image = args.get("has_image", False)
        image_path = args.get("image_path")

        # 如果未指定模型，自动分类
        if not model:
            classification = self.classifier.classify(task, has_image)
            model = classification.model

        if model == "cloud":
            return {
                "success": False,
                "message": "建议使用云端模型处理此任务",
                "model_used": "cloud"
            }

        # 构建并执行命令
        cmd = self._build_command(model, task, args)
        if image_path:
            cmd.extend(["--image", image_path])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            return {
                "success": proc.returncode == 0,
                "output": proc.stdout,
                "error": proc.stderr if proc.returncode != 0 else None,
                "model_used": model
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "本地模型执行超时（超过5分钟）",
                "model_used": model
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model_used": model
            }

    def _build_command(self, model: str, task: str, args: dict) -> list:
        """构建执行命令"""
        base_cmd = [
            "python3",
            "/Users/chenyousheng/.claude/skills/local-commander/local-commander.py",
            "--model", model,
            task
        ]

        # 添加额外参数
        if args.get("smart"):
            base_cmd.insert(-1, "--smart")
        if args.get("max_tokens"):
            base_cmd.insert(-1, "--max-tokens")
            base_cmd.insert(-1, str(args["max_tokens"]))

        return base_cmd

    # ========== 新增工具实现 ==========

    async def _review_code(self, args: dict) -> dict:
        """使用 27b 模型审查代码"""
        code = args.get("code", "")
        language = args.get("language", "auto")
        focus = args.get("focus", "all")

        focus_prompts = {
            "quality": "重点审查代码质量：可读性、可维护性、代码风格、命名规范",
            "security": "重点审查安全性：输入验证、注入风险、敏感数据处理、权限控制",
            "performance": "重点审查性能：算法复杂度、内存使用、数据库查询优化",
            "all": "全面审查：代码质量、安全性、性能、最佳实践"
        }

        review_prompt = f"""请审查以下 {language} 代码，{focus_prompts.get(focus, focus_prompts['all'])}。

代码：
```
{code}
```

请输出结构化审查报告：
1. 【评分】整体质量评分 (1-10)
2. 【问题】发现的问题列表（按严重程度排序）
3. 【建议】改进建议
4. 【优点】代码的优点

如果代码没有问题，直接说明"代码质量良好，无需修改"。"""

        try:
            proc = subprocess.run(
                [
                    "python3",
                    "/Users/chenyousheng/.claude/skills/local-commander/local-commander.py",
                    "--model", "27b",
                    review_prompt
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            return {
                "success": proc.returncode == 0,
                "review_report": proc.stdout if proc.returncode == 0 else None,
                "error": proc.stderr if proc.returncode != 0 else None,
                "model_used": "27b"
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "代码审查超时", "model_used": "27b"}
        except Exception as e:
            return {"success": False, "error": str(e), "model_used": "27b"}

    async def _fix_code(self, args: dict) -> dict:
        """使用 coder 模型修复代码问题"""
        code = args.get("code", "")
        issues = args.get("issues", "")
        language = args.get("language", "auto")

        fix_prompt = f"""请修复以下 {language} 代码的问题。

原始代码：
```
{code}
```

需要修复的问题：
{issues}

请输出修复后的完整代码，不要解释，只输出代码。"""

        try:
            proc = subprocess.run(
                [
                    "python3",
                    "/Users/chenyousheng/.claude/skills/local-commander/local-commander.py",
                    "--model", "coder",
                    fix_prompt
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            return {
                "success": proc.returncode == 0,
                "fixed_code": proc.stdout if proc.returncode == 0 else None,
                "error": proc.stderr if proc.returncode != 0 else None,
                "model_used": "coder"
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "代码修复超时", "model_used": "coder"}
        except Exception as e:
            return {"success": False, "error": str(e), "model_used": "coder"}

    async def _generate_with_review(self, args: dict) -> dict:
        """完整工作流：生成 → 审查 → 修复"""
        task = args.get("task", "")
        language = args.get("language", "TypeScript")
        max_fix_iterations = args.get("max_fix_iterations", 2)
        max_tokens = args.get("max_tokens", 8192)

        result = {
            "iterations": [],
            "final_code": None,
            "review_reports": [],
            "success": False
        }

        # Step 1: 生成代码
        generate_prompt = f"""请用 {language} 实现以下功能：

{task}

请输出完整、可运行的代码，包含必要的导入和类型定义。"""

        try:
            proc = subprocess.run(
                [
                    "python3",
                    "/Users/chenyousheng/.claude/skills/local-commander/local-commander.py",
                    "--model", "coder",
                    "--max-tokens", str(max_tokens),
                    generate_prompt
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            if proc.returncode != 0:
                return {"success": False, "error": f"代码生成失败: {proc.stderr}"}

            current_code = proc.stdout
            result["iterations"].append({"step": "generate", "success": True})

        except Exception as e:
            return {"success": False, "error": f"代码生成异常: {str(e)}"}

        # Step 2-3: 审查和修复循环
        for i in range(max_fix_iterations):
            # 审查代码
            review_result = await self._review_code({
                "code": current_code,
                "language": language,
                "focus": "all"
            })

            if not review_result["success"]:
                result["iterations"].append({"step": "review", "iteration": i + 1, "success": False})
                continue

            review_report = review_result["review_report"]
            result["review_reports"].append({"iteration": i + 1, "report": review_report})

            # 检查是否需要修复
            if "代码质量良好" in review_report or "无需修改" in review_report or "没有发现" in review_report:
                result["final_code"] = current_code
                result["success"] = True
                result["iterations"].append({"step": "review", "iteration": i + 1, "success": True, "needs_fix": False})
                break

            # 需要修复
            result["iterations"].append({"step": "review", "iteration": i + 1, "success": True, "needs_fix": True})

            # 修复代码
            fix_result = await self._fix_code({
                "code": current_code,
                "issues": review_report,
                "language": language
            })

            if not fix_result["success"]:
                result["iterations"].append({"step": "fix", "iteration": i + 1, "success": False})
                continue

            current_code = fix_result["fixed_code"]
            result["iterations"].append({"step": "fix", "iteration": i + 1, "success": True})

        # 最终结果
        if not result["success"]:
            result["final_code"] = current_code
            result["success"] = True  # 即使未通过审查，也返回最终代码

        return result

    # ========== UI 自动化测试工具实现 ==========

    async def _ui_screenshot(self, args: dict) -> dict:
        """使用 Playwright 截取网页截图"""
        url = args.get("url", "")
        output_path = args.get("output_path", "/tmp/ui-screenshot.png")
        width = args.get("viewport_width", 1400)
        height = args.get("viewport_height", 900)
        wait_time = args.get("wait_time", 2000)

        try:
            cmd = [
                "npx", "playwright", "screenshot",
                url, output_path,
                "--wait-for-timeout", str(wait_time),
                "--viewport-size", f"{width},{height}"
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if proc.returncode == 0:
                return {
                    "success": True,
                    "screenshot_path": output_path,
                    "url": url,
                    "message": f"截图已保存到 {output_path}"
                }
            else:
                return {
                    "success": False,
                    "error": proc.stderr or proc.stdout
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "截图超时"}
        except FileNotFoundError:
            return {"success": False, "error": "Playwright 未安装，请运行: npx playwright install"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ui_analyze_page(self, args: dict) -> dict:
        """截图并用 VL 模型分析页面"""
        url = args.get("url", "")
        analysis_prompt = args.get("analysis_prompt", "分析这个页面的功能、布局、UI设计，指出问题和改进建议")
        width = args.get("viewport_width", 1400)
        height = args.get("viewport_height", 900)

        # Step 1: 截图
        screenshot_result = await self._ui_screenshot({
            "url": url,
            "output_path": "/tmp/ui-analyze.png",
            "viewport_width": width,
            "viewport_height": height
        })

        if not screenshot_result["success"]:
            return {
                "success": False,
                "error": f"截图失败: {screenshot_result['error']}"
            }

        # Step 2: 调用 VL 模型分析
        try:
            proc = subprocess.run(
                [
                    "python3",
                    "/Users/chenyousheng/.claude/skills/local-commander/local-commander.py",
                    "--model", "vl",
                    "--image", "/tmp/ui-analyze.png",
                    analysis_prompt
                ],
                capture_output=True,
                text=True,
                timeout=180
            )

            if proc.returncode == 0:
                analysis = proc.stdout
                # 提取实际内容
                if "GenerationResult" in analysis:
                    import re
                    match = re.search(r"text='(.+?)', token=", analysis, re.DOTALL)
                    if match:
                        analysis = match.group(1).replace("\\n", "\n")

                return {
                    "success": True,
                    "url": url,
                    "screenshot_path": "/tmp/ui-analyze.png",
                    "analysis": analysis
                }
            else:
                return {
                    "success": False,
                    "error": f"VL 模型分析失败: {proc.stderr}"
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "VL 模型分析超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ui_test_pages(self, args: dict) -> dict:
        """批量测试多个页面"""
        base_url = args.get("base_url", "")
        pages = args.get("pages", [])
        page_names = args.get("page_names", [])

        if not pages:
            return {"success": False, "error": "未提供页面列表"}

        results = []
        passed = 0
        failed = 0

        for i, page in enumerate(pages):
            url = f"{base_url.rstrip('/')}/{page.lstrip('/')}"
            page_name = page_names[i] if i < len(page_names) else page

            # 分析页面
            result = await self._ui_analyze_page({
                "url": url,
                "analysis_prompt": f"分析这个 '{page_name}' 页面：1.页面是否正常加载 2.主要功能 3.是否有明显错误或问题。简洁回答。"
            })

            page_result = {
                "page": page_name,
                "url": url,
                "success": result["success"]
            }

            if result["success"]:
                page_result["analysis"] = result.get("analysis", "")
                # 检查是否有错误关键词
                analysis_lower = result.get("analysis", "").lower()
                if "错误" in analysis_lower or "error" in analysis_lower or "失败" in analysis_lower:
                    page_result["status"] = "warning"
                else:
                    page_result["status"] = "passed"
                    passed += 1
            else:
                page_result["error"] = result.get("error", "")
                page_result["status"] = "failed"
                failed += 1

            results.append(page_result)

        return {
            "success": True,
            "summary": {
                "total": len(pages),
                "passed": passed,
                "failed": failed
            },
            "results": results
        }

    async def _ui_click_and_verify(self, args: dict) -> dict:
        """点击元素并验证结果"""
        url = args.get("url", "")
        selector = args.get("selector", "")
        verify_type = args.get("verify_type", "screenshot")
        verify_target = args.get("verify_target", "")

        # 这里需要使用 Playwright 的完整脚本
        script = f'''
const {{ chromium }} = require('playwright');

(async () => {{
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('{url}');
    await page.waitForTimeout(1000);

    // 点击元素
    try {{
        await page.click('{selector}');
        await page.waitForTimeout(1000);
    }} catch (e) {{
        console.error('Click failed:', e.message);
        await browser.close();
        process.exit(1);
    }}
'''

        if verify_type == "screenshot":
            script += f'''
    // 截图验证
    await page.screenshot({{ path: '/tmp/ui-click-result.png' }});
    console.log('Screenshot saved');
'''
        elif verify_type == "text":
            script += f'''
    // 文本验证
    const text = await page.textContent('body');
    if (text.includes('{verify_target}')) {{
        console.log('Text found:', '{verify_target}');
    }} else {{
        console.log('Text not found');
    }}
'''
        elif verify_type == "element":
            script += f'''
    // 元素验证
    const element = await page.$('{verify_target}');
    if (element) {{
        console.log('Element found');
    }} else {{
        console.log('Element not found');
    }}
'''

        script += '''
    await browser.close();
})();
'''

        try:
            # 写入临时脚本
            script_path = "/tmp/playwright-test.js"
            with open(script_path, "w") as f:
                f.write(script)

            proc = subprocess.run(
                ["node", script_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if proc.returncode == 0:
                return {
                    "success": True,
                    "url": url,
                    "selector": selector,
                    "verify_type": verify_type,
                    "output": proc.stdout
                }
            else:
                return {
                    "success": False,
                    "error": proc.stderr or proc.stdout
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== 增强版 UI 测试工具实现 ==========
    async def _ui_test_spa(self, args: dict) -> dict:
        """SPA 应用路由测试 - 通过菜单点击测试不同页面"""
        url = args.get("url", "")
        routes = args.get("routes", [])
        width = args.get("viewport_width", 1200)
        height = args.get("viewport_height", 800)

        if not routes:
            return {"success": False, "error": "未提供路由配置"}

        # 生成 Playwright 测试脚本
        routes_json = json.dumps(routes, ensure_ascii=False)
        script = f'''
const {{ chromium }} = require('playwright');

const routes = {routes_json};

(async () => {{
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.setViewportSize({{ width: {width}, height: {height} }});

    const results = [];

    try {{
        await page.goto('{url}');
        await page.waitForTimeout(2000);

        for (const route of routes) {{
            const result = {{ name: route.name, success: false }};

            try {{
                // 通过文本内容查找并点击菜单
                const menuItems = await page.$$('.ant-menu-item');
                let clicked = false;

                for (const item of menuItems) {{
                    const text = await item.textContent();
                    if (text && text.includes(route.menu_text)) {{
                        await item.click();
                        clicked = true;
                        break;
                    }}
                }}

                if (!clicked) {{
                    // 尝试其他选择器
                    await page.click(`text=${{route.menu_text}}`).catch(() => {{}});
                }}

                await page.waitForTimeout(1000);

                // 截图
                const screenshotPath = `/tmp/spa-${{route.name.replace(/\\s+/g, '-')}}.png`;
                await page.screenshot({{ path: screenshotPath }});

                // 检查期望元素
                let elementsFound = [];
                if (route.expected_elements) {{
                    for (const elem of route.expected_elements) {{
                        const found = await page.locator(`text=${{elem}}`).count() > 0;
                        if (found) elementsFound.push(elem);
                    }}
                }}

                result.success = true;
                result.screenshot = screenshotPath;
                result.elements_found = elementsFound;

            }} catch (e) {{
                result.error = e.message;
            }}

            results.push(result);
        }}

        console.log(JSON.stringify(results));

    }} catch (e) {{
        console.error(JSON.stringify({{ error: e.message }}));
    }} finally {{
        await browser.close();
    }}
}})();
'''

        try:
            script_path = "/tmp/playwright-spa-test.js"
            with open(script_path, "w") as f:
                f.write(script)

            proc = subprocess.run(
                ["node", script_path],
                capture_output=True,
                text=True,
                timeout=120
            )

            if proc.returncode == 0:
                try:
                    results = json.loads(proc.stdout.strip().split('\n')[-1])
                except:
                    results = [{"raw": proc.stdout}]

                passed = sum(1 for r in results if r.get("success"))

                return {
                    "success": True,
                    "url": url,
                    "summary": {
                        "total": len(routes),
                        "passed": passed,
                        "failed": len(routes) - passed
                    },
                    "results": results
                }
            else:
                return {"success": False, "error": proc.stderr or proc.stdout}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ui_interact(self, args: dict) -> dict:
        """高级交互测试"""
        url = args.get("url", "")
        steps = args.get("steps", [])
        screenshot_on_complete = args.get("screenshot_on_complete", True)

        # 生成动态脚本
        script_lines = [
            "const { chromium } = require('playwright');",
            "(async () => {",
            "    const browser = await chromium.launch();",
            "    const page = await browser.newPage();",
            f"    await page.goto('{url}');",
            "    await page.waitForTimeout(1000);",
            "    const logs = [];"
        ]

        for i, step in enumerate(steps):
            action = step.get("action")
            selector = step.get("selector", "")
            value = step.get("value", "")
            timeout = step.get("timeout", 5000)

            if action == "click":
                # 支持文本选择器
                if not selector.startswith(".") and not selector.startswith("#") and not selector.startswith("["):
                    script_lines.append(f"    await page.locator('text={selector}').first().click().catch(e => logs.push('Step {i}: Click failed - ' + e.message));")
                else:
                    script_lines.append(f"    await page.click('{selector}').catch(e => logs.push('Step {i}: Click failed - ' + e.message));")

            elif action == "fill":
                script_lines.append(f"    await page.fill('{selector}', '{value}').catch(e => logs.push('Step {i}: Fill failed - ' + e.message));")

            elif action == "select":
                script_lines.append(f"    await page.selectOption('{selector}', '{value}').catch(e => logs.push('Step {i}: Select failed - ' + e.message));")

            elif action == "press":
                script_lines.append(f"    await page.keyboard.press('{value}').catch(e => logs.push('Step {i}: Press failed - ' + e.message));")

            elif action == "wait":
                script_lines.append(f"    await page.waitForTimeout({timeout});")

            elif action == "screenshot":
                script_lines.append(f"    await page.screenshot({{ path: '/tmp/ui-interact-{i}.png' }});")
                script_lines.append(f"    logs.push('Screenshot saved: /tmp/ui-interact-{i}.png');")

            elif action == "assert_text":
                script_lines.append(f"""    {{
        const text = await page.textContent('body');
        if (!text.includes('{value}')) {{
            logs.push('Step {i}: Text not found: {value}');
            console.log(JSON.stringify({{ success: false, error: 'Assertion failed: text not found', logs }}));
            await browser.close();
            process.exit(1);
        }} else {{
            logs.push('Step {i}: Text found: {value}');
        }}
    }}""")

            elif action == "assert_element":
                script_lines.append(f"    const count = await page.locator('{selector}').count();")
                script_lines.append(f"    if (count === 0) logs.push('Step {i}: Element not found: {selector}');")
                script_lines.append(f"    else logs.push('Step {i}: Element found: {selector}');")

            script_lines.append(f"    await page.waitForTimeout(300);")

        if screenshot_on_complete:
            script_lines.append("    await page.screenshot({ path: '/tmp/ui-interact-final.png' });")

        script_lines.extend([
            "    console.log(JSON.stringify({ success: true, logs }));",
            "    await browser.close();",
            "})();"
        ])

        script = "\n".join(script_lines)

        try:
            script_path = "/tmp/playwright-interact.js"
            with open(script_path, "w") as f:
                f.write(script)

            proc = subprocess.run(
                ["node", script_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            if proc.returncode == 0:
                try:
                    result = json.loads(proc.stdout.strip().split('\n')[-1])
                except:
                    result = {"success": True, "raw": proc.stdout}
                return {
                    "success": result.get("success", True),
                    "url": url,
                    "steps_executed": len(steps),
                    "logs": result.get("logs", []),
                    "screenshot": "/tmp/ui-interact-final.png" if screenshot_on_complete else None
                }
            else:
                return {"success": False, "error": proc.stderr or proc.stdout}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ui_desktop_app(self, args: dict) -> dict:
        """桌面应用测试（Tauri/Electron）"""
        import socket
        import time

        port = args.get("port")
        wait_for_ready = args.get("wait_for_ready", True)
        timeout = args.get("timeout", 30000)
        test_routes = args.get("test_routes", [])

        # 自动检测端口（常见开发端口）
        common_ports = [1420, 3000, 5173, 8080, 5174]
        detected_port = None

        if port:
            ports_to_check = [port]
        else:
            ports_to_check = common_ports

        # 检测可用端口
        for p in ports_to_check:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', p))
            sock.close()
            if result == 0:
                detected_port = p
                break

        if not detected_port:
            return {
                "success": False,
                "error": "未检测到运行中的本地服务",
                "checked_ports": ports_to_check
            }

        url = f"http://localhost:{detected_port}"

        # 等待服务就绪
        if wait_for_ready:
            start_time = time.time()
            ready = False
            while time.time() - start_time < timeout / 1000:
                try:
                    import urllib.request
                    urllib.request.urlopen(url, timeout=2)
                    ready = True
                    break
                except:
                    time.sleep(0.5)

            if not ready:
                return {"success": False, "error": f"服务就绪超时: {url}"}

        # 执行路由测试
        if test_routes:
            spa_result = await self._ui_test_spa({
                "url": url,
                "routes": test_routes
            })
            return {
                "success": spa_result.get("success", False),
                "url": url,
                "port": detected_port,
                "test_result": spa_result
            }

        return {
            "success": True,
            "url": url,
            "port": detected_port,
            "message": f"检测到服务运行在 {url}"
        }

    def _ui_generate_report(self, args: dict) -> dict:
        """生成 HTML 测试报告"""
        title = args.get("title", "UI 自动化测试报告")
        test_results = args.get("test_results", [])
        output_path = args.get("output_path", "/tmp/ui-test-report.html")

        # 统计
        total = len(test_results)
        passed = sum(1 for r in test_results if r.get("status") == "passed" or r.get("success"))
        failed = total - passed

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 32px; font-weight: bold; }}
        .stat-label {{ color: #666; }}
        .passed .stat-value {{ color: #52c41a; }}
        .failed .stat-value {{ color: #ff4d4f; }}
        .results {{ background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .result-item {{ padding: 15px 20px; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 15px; }}
        .result-item:last-child {{ border-bottom: none; }}
        .status {{ width: 10px; height: 10px; border-radius: 50%; }}
        .status.passed {{ background: #52c41a; }}
        .status.failed {{ background: #ff4d4f; }}
        .timestamp {{ color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 {title}</h1>
        <p class="timestamp">生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

        <div class="summary">
            <div class="stat">
                <div class="stat-value">{total}</div>
                <div class="stat-label">总计</div>
            </div>
            <div class="stat passed">
                <div class="stat-value">{passed}</div>
                <div class="stat-label">通过</div>
            </div>
            <div class="stat failed">
                <div class="stat-value">{failed}</div>
                <div class="stat-label">失败</div>
            </div>
        </div>

        <div class="results">
            <h3 style="padding: 15px 20px; margin: 0; background: #fafafa;">测试结果详情</h3>
'''

        for r in test_results:
            status_class = "passed" if r.get("status") == "passed" or r.get("success") else "failed"
            status_text = "✅ 通过" if status_class == "passed" else "❌ 失败"
            html += f'''
            <div class="result-item">
                <div class="status {status_class}"></div>
                <div>
                    <strong>{r.get('name', r.get('page', '未知测试'))}</strong>
                    <div style="color: #666; font-size: 14px;">{status_text}</div>
                </div>
            </div>'''

        html += '''
        </div>
    </div>
</body>
</html>'''

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return {
            "success": True,
            "report_path": output_path,
            "summary": {"total": total, "passed": passed, "failed": failed}
        }

    # ========== 原生窗口测试工具实现 ==========
    def _native_window_list(self, args: dict) -> dict:
        """列出 macOS 原生应用窗口"""
        app_filter = args.get("app_name")

        try:
            import subprocess

            # 使用 AppleScript 获取窗口列表
            script = '''
            tell application "System Events"
                set output to ""
                repeat with theProcess in (every process whose background only is false)
                    try
                        set appName to name of theProcess
                        set windowList to name of every window of theProcess
                        if windowList is not {} then
                            set output to output & appName & ":" & (item 1 of windowList) & linefeed
                        end if
                    end try
                end repeat
                return output
            end tell
            '''

            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if proc.returncode != 0:
                return {"success": False, "error": proc.stderr}

            # 解析输出
            windows = []
            for line in proc.stdout.strip().split('\n'):
                if ':' in line:
                    app_name, window_title = line.split(':', 1)
                    if app_filter is None or app_filter.lower() in app_name.lower():
                        windows.append({
                            "app_name": app_name,
                            "window_title": window_title
                        })

            return {
                "success": True,
                "count": len(windows),
                "windows": windows
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _native_window_elements(self, args: dict) -> dict:
        """获取原生窗口的 UI 元素树"""
        app_name = args.get("app_name")
        window_title = args.get("window_title", "")

        try:
            import subprocess

            # 使用 AppleScript 获取窗口元素
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    try
                        set frontWindow to front window
                        set elementList to {{}}

                        repeat with theElement in entire contents of frontWindow
                            try
                                set elemDesc to description of theElement
                                set elemRole to role of theElement
                                set elemName to name of theElement
                                set elemValue to value of theElement
                                set end of elementList to elemRole & "|" & elemName & "|" & elemDesc & "|" & elemValue
                            end try
                        end repeat

                        return elementList as string
                    on error errMsg
                        return "Error: " & errMsg
                    end try
                end tell
            end tell
            '''

            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if "Error:" in proc.stdout:
                return {"success": False, "error": proc.stdout.split("Error:")[1].strip()}

            # 解析元素
            elements = []
            raw_elements = proc.stdout.replace('{', '').replace('}', '').split(',')

            for elem in raw_elements:
                parts = elem.strip().split('|')
                if len(parts) >= 2:
                    elements.append({
                        "role": parts[0].strip() if len(parts) > 0 else "",
                        "name": parts[1].strip() if len(parts) > 1 else "",
                        "description": parts[2].strip() if len(parts) > 2 else "",
                        "value": parts[3].strip() if len(parts) > 3 else ""
                    })

            return {
                "success": True,
                "app_name": app_name,
                "count": len(elements),
                "elements": elements[:50]  # 限制返回数量
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _native_window_action(self, args: dict) -> dict:
        """对原生窗口执行操作"""
        app_name = args.get("app_name")
        action = args.get("action")
        element = args.get("element", "")
        value = args.get("value", "")

        try:
            import subprocess

            if action == "click":
                script = f'''
                tell application "System Events"
                    tell process "{app_name}"
                        try
                            click button "{element}" of front window
                            return "Clicked: {element}"
                        on error
                            try
                                click static text "{element}" of front window
                                return "Clicked text: {element}"
                            on error errMsg
                                return "Error: " & errMsg
                            end try
                        end try
                    end tell
                end tell
                '''

            elif action == "input":
                script = f'''
                tell application "System Events"
                    tell process "{app_name}"
                        try
                            keystroke "{value}"
                            return "Typed: {value}"
                        on error errMsg
                            return "Error: " & errMsg
                        end try
                    end tell
                end tell
                '''

            elif action == "press_key":
                script = f'''
                tell application "System Events"
                    tell process "{app_name}"
                        try
                            keystroke "{value}"
                            return "Pressed: {value}"
                        on error errMsg
                            return "Error: " & errMsg
                        end try
                    end tell
                end tell
                '''

            elif action == "get_text":
                script = f'''
                tell application "System Events"
                    tell process "{app_name}"
                        try
                            return value of static text 1 of front window
                        on error errMsg
                            return "Error: " & errMsg
                        end try
                    end tell
                end tell
                '''

            elif action == "screenshot":
                screenshot_path = f"/tmp/native-{app_name}.png"
                script = f'''
                do shell script "screencapture -x '{screenshot_path}'"
                return "Screenshot saved to {screenshot_path}"
                '''

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if "Error:" in proc.stdout:
                return {"success": False, "error": proc.stdout.split("Error:")[1].strip()}

            return {
                "success": True,
                "app_name": app_name,
                "action": action,
                "result": proc.stdout.strip()
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== API 测试工具实现 ==========
    async def _api_request(self, args: dict) -> dict:
        """发送 HTTP API 请求"""
        import urllib.request
        import urllib.error
        import time

        method = args.get("method", "GET")
        url = args.get("url")
        headers = args.get("headers", {})
        body = args.get("body")
        timeout = args.get("timeout", 30)

        if not url:
            return {"success": False, "error": "URL is required"}

        start_time = time.time()

        try:
            # 准备请求
            req_data = None
            if body and method in ["POST", "PUT", "PATCH"]:
                req_data = json.dumps(body).encode('utf-8')
                if 'Content-Type' not in headers:
                    headers['Content-Type'] = 'application/json'

            request = urllib.request.Request(
                url,
                data=req_data,
                headers=headers,
                method=method
            )

            # 发送请求
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_time = (time.time() - start_time) * 1000
                response_body = response.read().decode('utf-8')

                try:
                    response_json = json.loads(response_body)
                except:
                    response_json = None

                return {
                    "success": True,
                    "status_code": response.status,
                    "response_time_ms": round(response_time, 2),
                    "headers": dict(response.headers),
                    "body": response_json if response_json else response_body[:1000]
                }

        except urllib.error.HTTPError as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "status_code": e.code,
                "response_time_ms": round(response_time, 2),
                "error": str(e)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _api_test_sequence(self, args: dict) -> dict:
        """批量 API 测试"""
        base_url = args.get("base_url", "").rstrip('/')
        tests = args.get("tests", [])
        auth_token = args.get("auth_token")

        if not tests:
            return {"success": False, "error": "No tests provided"}

        results = []
        passed = 0
        failed = 0

        for test in tests:
            name = test.get("name", "Unnamed")
            method = test.get("method", "GET")
            path = test.get("path", "")
            expected_status = test.get("expected_status", 200)
            expected_fields = test.get("expected_fields", [])

            url = f"{base_url}{path}"
            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            # 发送请求
            result = await self._api_request({
                "method": method,
                "url": url,
                "headers": headers
            })

            test_result = {
                "name": name,
                "url": url,
                "method": method
            }

            if result.get("success"):
                # 检查状态码
                status_ok = result.get("status_code") == expected_status

                # 检查期望字段
                fields_found = []
                fields_missing = []
                if expected_fields and result.get("body"):
                    body = result["body"]
                    if isinstance(body, dict):
                        for field in expected_fields:
                            if field in body:
                                fields_found.append(field)
                            else:
                                fields_missing.append(field)

                test_result["status_code"] = result.get("status_code")
                test_result["response_time_ms"] = result.get("response_time_ms")
                test_result["status_ok"] = status_ok
                test_result["fields_found"] = fields_found

                if status_ok and not fields_missing:
                    test_result["status"] = "passed"
                    passed += 1
                else:
                    test_result["status"] = "failed"
                    test_result["missing_fields"] = fields_missing
                    failed += 1
            else:
                test_result["status"] = "failed"
                test_result["error"] = result.get("error")
                failed += 1

            results.append(test_result)

        return {
            "success": True,
            "base_url": base_url,
            "summary": {
                "total": len(tests),
                "passed": passed,
                "failed": failed
            },
            "results": results
        }

    # ========== iOS 模拟器测试工具实现 ==========
    def _ios_simulator_list(self, args: dict) -> dict:
        """列出可用的 iOS 模拟器"""
        state_filter = args.get("state", "all")

        try:
            # 获取模拟器列表
            proc = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "-j"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if proc.returncode != 0:
                return {"success": False, "error": proc.stderr}

            data = json.loads(proc.stdout)
            devices = []

            for runtime, device_list in data.get("devices", {}).items():
                for device in device_list:
                    device_state = device.get("state", "").lower()
                    name = device.get("name", "")
                    udid = device.get("udid", "")

                    # 筛选状态
                    if state_filter == "booted" and device_state != "booted":
                        continue
                    if state_filter == "shutdown" and device_state != "shutdown":
                        continue

                    devices.append({
                        "name": name,
                        "udid": udid,
                        "state": device_state,
                        "runtime": runtime
                    })

            return {
                "success": True,
                "count": len(devices),
                "devices": devices
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ios_simulator_control(self, args: dict) -> dict:
        """控制 iOS 模拟器"""
        action = args.get("action")
        device = args.get("device")

        if not device:
            return {"success": False, "error": "设备名称或 UDID 必须提供"}

        try:
            if action == "boot":
                proc = subprocess.run(
                    ["xcrun", "simctl", "boot", device],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                # 打开模拟器窗口
                subprocess.run(["open", "-a", "Simulator"], capture_output=True)

            elif action == "shutdown":
                proc = subprocess.run(
                    ["xcrun", "simctl", "shutdown", device],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

            elif action == "restart":
                # 先关闭再启动
                subprocess.run(
                    ["xcrun", "simctl", "shutdown", device],
                    capture_output=True,
                    timeout=30
                )
                proc = subprocess.run(
                    ["xcrun", "simctl", "boot", device],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

            elif action == "erase":
                proc = subprocess.run(
                    ["xcrun", "simctl", "erase", device],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            else:
                return {"success": False, "error": f"未知操作: {action}"}

            if proc.returncode == 0 or "already" in proc.stderr.lower():
                return {
                    "success": True,
                    "action": action,
                    "device": device,
                    "message": f"模拟器 {action} 成功"
                }
            else:
                return {
                    "success": False,
                    "error": proc.stderr or "操作失败"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ios_simulator_screenshot(self, args: dict) -> dict:
        """截取 iOS 模拟器屏幕"""
        device = args.get("device", "")
        save_path = args.get("save_path", "/tmp/ios-screenshot.png")

        try:
            # 如果没有指定设备，尝试获取已启动的设备
            if not device:
                list_result = self._ios_simulator_list({"state": "booted"})
                if list_result.get("success") and list_result.get("devices"):
                    device = list_result["devices"][0]["udid"]
                else:
                    return {"success": False, "error": "没有已启动的模拟器"}

            proc = subprocess.run(
                ["xcrun", "simctl", "io", device, "screenshot", save_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if proc.returncode == 0:
                return {
                    "success": True,
                    "device": device,
                    "screenshot_path": save_path
                }
            else:
                return {"success": False, "error": proc.stderr}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ios_simulator_action(self, args: dict) -> dict:
        """在 iOS 模拟器上执行操作"""
        action = args.get("action")
        device = args.get("device", "")
        x = args.get("x", 0)
        y = args.get("y", 0)
        end_x = args.get("end_x", 0)
        end_y = args.get("end_y", 0)
        text = args.get("text", "")
        key = args.get("key", "")

        try:
            # 获取已启动的设备
            if not device:
                list_result = self._ios_simulator_list({"state": "booted"})
                if list_result.get("success") and list_result.get("devices"):
                    device = list_result["devices"][0]["udid"]
                else:
                    return {"success": False, "error": "没有已启动的模拟器"}

            if action == "tap":
                # 使用 AppleScript 进行点击
                script = f'''
                tell application "Simulator"
                    activate
                end tell
                tell application "System Events"
                    tell process "Simulator"
                        try
                            click at {{{x}, {y}}}
                            return "Tapped at ({x}, {y})"
                        on error errMsg
                            return "Error: " & errMsg
                        end try
                    end tell
                end tell
                '''
                proc = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            elif action == "input":
                # 输入文本
                script = f'''
                tell application "Simulator"
                    activate
                end tell
                tell application "System Events"
                    tell process "Simulator"
                        keystroke "{text}"
                    end tell
                end tell
                return "Typed: {text}"
                '''
                proc = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            elif action == "press_key":
                # 按键
                script = f'''
                tell application "Simulator"
                    activate
                end tell
                tell application "System Events"
                    tell process "Simulator"
                        keystroke "{key}"
                    end tell
                end tell
                return "Pressed: {key}"
                '''
                proc = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            elif action == "swipe":
                # 滑动 (通过多次点击模拟)
                script = f'''
                tell application "Simulator"
                    activate
                end tell
                tell application "System Events"
                    tell process "Simulator"
                        -- Simple swipe simulation
                        click at {{{x}, {y}}}
                        delay 0.1
                        click at {{{end_x}, {end_y}}}
                    end tell
                end tell
                return "Swiped from ({x}, {y}) to ({end_x}, {end_y})"
                '''
                proc = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            elif action == "home":
                # Home 键
                proc = subprocess.run(
                    ["xcrun", "simctl", "io", device, "pressButton", "home"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            elif action == "siri":
                # Siri
                proc = subprocess.run(
                    ["xcrun", "simctl", "io", device, "pressButton", "siri"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            else:
                return {"success": False, "error": f"未知操作: {action}"}

            if "Error:" in proc.stdout:
                return {"success": False, "error": proc.stdout.split("Error:")[1].strip()}

            return {
                "success": True,
                "action": action,
                "device": device,
                "result": proc.stdout.strip() if proc.stdout else "OK"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ios_simulator_app(self, args: dict) -> dict:
        """管理 iOS 模拟器中的应用"""
        action = args.get("action")
        device = args.get("device", "")
        app_path = args.get("app_path", "")
        bundle_id = args.get("bundle_id", "")

        try:
            # 获取已启动的设备
            if not device:
                list_result = self._ios_simulator_list({"state": "booted"})
                if list_result.get("success") and list_result.get("devices"):
                    device = list_result["devices"][0]["udid"]
                else:
                    return {"success": False, "error": "没有已启动的模拟器"}

            if action == "install":
                if not app_path:
                    return {"success": False, "error": "需要提供应用路径"}
                proc = subprocess.run(
                    ["xcrun", "simctl", "install", device, app_path],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                return {
                    "success": proc.returncode == 0,
                    "action": "install",
                    "error": proc.stderr if proc.returncode != 0 else None
                }

            elif action == "launch":
                if not bundle_id:
                    return {"success": False, "error": "需要提供 Bundle ID"}
                proc = subprocess.run(
                    ["xcrun", "simctl", "launch", device, bundle_id],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    "success": proc.returncode == 0,
                    "action": "launch",
                    "bundle_id": bundle_id,
                    "error": proc.stderr if proc.returncode != 0 else None
                }

            elif action == "terminate":
                if not bundle_id:
                    return {"success": False, "error": "需要提供 Bundle ID"}
                proc = subprocess.run(
                    ["xcrun", "simctl", "terminate", device, bundle_id],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    "success": proc.returncode == 0,
                    "action": "terminate",
                    "bundle_id": bundle_id
                }

            elif action == "uninstall":
                if not bundle_id:
                    return {"success": False, "error": "需要提供 Bundle ID"}
                proc = subprocess.run(
                    ["xcrun", "simctl", "uninstall", device, bundle_id],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    "success": proc.returncode == 0,
                    "action": "uninstall",
                    "bundle_id": bundle_id
                }

            elif action == "list":
                proc = subprocess.run(
                    ["xcrun", "simctl", "listapps", device],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                # 解析应用列表
                apps = []
                for line in proc.stdout.split('\n'):
                    if 'BundleID' in line:
                        bundle = line.split('=')[-1].strip()
                        apps.append({"bundle_id": bundle})

                return {
                    "success": True,
                    "count": len(apps),
                    "apps": apps[:20]  # 限制返回数量
                }

            else:
                return {"success": False, "error": f"未知操作: {action}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== iOS 真机测试工具实现 ==========
    def _ios_device_list(self, args: dict) -> dict:
        """列出连接的 iOS 真机设备"""
        try:
            # 检查是否安装了 libimobiledevice
            proc = subprocess.run(
                ["which", "idevice_id"],
                capture_output=True,
                text=True
            )

            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": "未安装 libimobiledevice，请运行: brew install libimobiledevice",
                    "hint": "需要 USB 连接设备并在设备上信任此电脑"
                }

            # 获取设备列表
            proc = subprocess.run(
                ["idevice_id", "-l"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if proc.returncode != 0:
                return {"success": False, "error": proc.stderr}

            devices = []
            for line in proc.stdout.strip().split('\n'):
                if line.strip():
                    devices.append({"udid": line.strip()})

            return {
                "success": True,
                "count": len(devices),
                "devices": devices,
                "message": f"发现 {len(devices)} 台设备" if devices else "没有连接的设备"
            }

        except FileNotFoundError:
            return {
                "success": False,
                "error": "未安装 libimobiledevice",
                "hint": "brew install libimobiledevice"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ios_device_screenshot(self, args: dict) -> dict:
        """截取 iOS 真机屏幕"""
        udid = args.get("udid", "")
        save_path = args.get("save_path", "/tmp/ios-device-screenshot.png")

        try:
            # 检查工具
            proc = subprocess.run(
                ["which", "idevicescreenshot"],
                capture_output=True,
                text=True
            )

            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": "未安装 libimobiledevice，请运行: brew install libimobiledevice"
                }

            # 截图
            cmd = ["idevicescreenshot", save_path]
            if udid:
                cmd.extend(["-u", udid])

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if proc.returncode == 0:
                return {
                    "success": True,
                    "screenshot_path": save_path
                }
            else:
                return {
                    "success": False,
                    "error": proc.stderr or "截图失败，请确保设备已信任此电脑"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== AI 知识库工具实现 ==========
    def _get_kb(self):
        """获取知识库实例 (ChromaDB 版本)"""
        from knowledge_base_chroma import get_knowledge_base
        return get_knowledge_base()

    def _kb_add(self, args: dict) -> dict:
        """添加知识点"""
        kb = self._get_kb()
        item = kb.add(
            text=args.get("text", ""),
            category=args.get("category", "general"),
            tags=args.get("tags", []),
            importance=args.get("importance", 0.5)
        )
        return {
            "success": True,
            "id": item["id"],
            "summary": item["summary"],
            "category": item["category"],
            "tags": item["tags"]
        }

    def _kb_search(self, args: dict) -> dict:
        """搜索知识库"""
        kb = self._get_kb()
        results = kb.search(
            query=args.get("query", ""),
            top_k=args.get("top_k", 5),
            category=args.get("category"),
            tags=args.get("tags")
        )
        return {
            "success": True,
            "query": args.get("query"),
            "count": len(results),
            "results": results
        }

    def _kb_list(self, args: dict) -> dict:
        """列出知识点"""
        kb = self._get_kb()
        items = kb.list(
            category=args.get("category"),
            tags=args.get("tags"),
            limit=args.get("limit", 20)
        )
        return {
            "success": True,
            "count": len(items),
            "items": items
        }

    def _kb_stats(self) -> dict:
        """知识库统计"""
        kb = self._get_kb()
        return {
            "success": True,
            **kb.stats()
        }

    def _kb_delete(self, args: dict) -> dict:
        """删除知识点"""
        kb = self._get_kb()
        kb_id = args.get("id", "")
        success = kb.delete(kb_id)
        return {
            "success": success,
            "id": kb_id,
            "message": "已删除" if success else "未找到"
        }

    # ========== Android UI 自动化工具实现 ==========
    def _get_android_automation(self, device_serial: str = None):
        """获取 Android 自动化实例"""
        from android_ui_automation import AndroidUIAutomation
        if device_serial:
            return AndroidUIAutomation(device_serial)
        return AndroidUIAutomation()

    def _android_dump_ui(self, args: dict) -> dict:
        """获取 Android UI 元素"""
        try:
            auto = self._get_android_automation(args.get("device_serial"))
            ui = auto.dump_ui()

            # 只返回可点击且有内容的元素
            clickable = [
                {
                    "text": e.get("text", ""),
                    "content_desc": e.get("content_desc", ""),
                    "resource_id": e.get("resource_id", ""),
                    "class": e.get("class", ""),
                    "bounds": e.get("bounds", "")
                }
                for e in ui.get("elements", [])
                if e.get("clickable") and (e.get("text") or e.get("content_desc"))
            ]

            return {
                "success": True,
                "device": ui.get("device"),
                "total_elements": ui.get("element_count", 0),
                "clickable_elements": len(clickable),
                "elements": clickable
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _android_tap(self, args: dict) -> dict:
        """点击 Android 元素"""
        try:
            auto = self._get_android_automation(args.get("device_serial"))

            # 坐标点击
            if args.get("x") and args.get("y"):
                success = auto.tap(args["x"], args["y"])
                return {"success": success, "action": "tap_coords", "coords": (args["x"], args["y"])}

            # 元素定位点击
            success = auto.tap_element(
                text=args.get("text"),
                resource_id=args.get("resource_id"),
                content_desc=args.get("content_desc")
            )
            return {
                "success": success,
                "action": "tap_element",
                "target": args.get("text") or args.get("resource_id") or args.get("content_desc")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _android_screenshot(self, args: dict) -> dict:
        """Android 截图"""
        try:
            auto = self._get_android_automation()
            save_path = args.get("save_path", "/tmp/android_screenshot.png")
            path = auto.screenshot(save_path)
            return {"success": True, "screenshot_path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _android_run_test(self, args: dict) -> dict:
        """运行 Android 测试序列"""
        try:
            auto = self._get_android_automation()
            steps = args.get("steps", [])
            result = auto.run_test_sequence(steps)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}


async def main():
    """主入口 - 实现 MCP stdio 协议"""
    server = MCPRouterServer()

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line.strip())
            response = await server.handle_request(request)

            # 有些通知不需要响应
            if response is not None:
                print(json.dumps(response), flush=True)

        except json.JSONDecodeError as e:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }), flush=True)
        except Exception as e:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": f"Internal error: {e}"}
            }), flush=True)


if __name__ == "__main__":
    asyncio.run(main())