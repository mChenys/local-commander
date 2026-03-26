#!/usr/bin/env python3
"""
Local Commander MCP Router Service
MCP 标准协议服务器 - 自动识别任务类型并路由到合适的本地模型
"""

import json
import sys
import asyncio
import subprocess
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