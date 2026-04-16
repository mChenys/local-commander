#!/usr/bin/env python3
"""
Local Commander CLI - 本地模型指挥官命令行工具
"""

import sys
import os
import re
import json
import argparse
from datetime import datetime
from pathlib import Path

# 添加 lib 目录到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from lib.router import get_router
from lib.session import get_session_manager
from lib.embedder import get_embedder, KnowledgeBase
from lib.knowledge_base import get_knowledge_base
from enhancements import (
    get_system_info, validate_model_configuration,
    benchmark_model, generate_performance_report,
    optimize_project_scanning, setup_optimized_config,
    optimize_cli_arguments
)


def extract_code_blocks(text: str) -> list:
    """从文本中提取代码块"""
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [(lang or "txt", code.strip()) for lang, code in matches]


def detect_project_type(work_dir: Path) -> dict:
    """检测项目类型"""
    project_info = {
        "type": "unknown",
        "source_dir": None,
        "lang": None
    }

    # Android 项目
    if (work_dir / "build.gradle").exists() or (work_dir / "build.gradle.kts").exists():
        project_info["type"] = "android"
        project_info["lang"] = "kotlin"
        # 查找源码目录
        src_dirs = list(work_dir.rglob("src/main/java")) + list(work_dir.rglob("src/main/kotlin"))
        if src_dirs:
            project_info["source_dir"] = src_dirs[0]

    # iOS 项目
    elif list(work_dir.glob("*.xcodeproj")) or list(work_dir.glob("*.xcworkspace")):
        project_info["type"] = "ios"
        project_info["lang"] = "swift"

    # Node.js / Web 项目
    elif (work_dir / "package.json").exists():
        project_info["type"] = "web"
        project_info["lang"] = "javascript"
        if (work_dir / "src").exists():
            project_info["source_dir"] = work_dir / "src"

    # Python 项目
    elif (work_dir / "requirements.txt").exists() or (work_dir / "setup.py").exists():
        project_info["type"] = "python"
        project_info["lang"] = "python"

    return project_info


def save_code_to_project(code_blocks: list, work_dir: Path, project_info: dict) -> list:
    """智能保存代码到项目"""
    saved_files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i, (lang, code) in enumerate(code_blocks):
        # 根据项目类型和语言确定保存位置
        save_dir = work_dir

        if project_info["type"] == "android" and lang.lower() == "kotlin":
            # Android 项目：保存到 src/main/kotlin (如果存在)
            if project_info["source_dir"]:
                save_dir = project_info["source_dir"]
            elif (work_dir / "app" / "src" / "main" / "kotlin").exists():
                save_dir = work_dir / "app" / "src" / "main" / "kotlin"
            else:
                save_dir = work_dir / "generated"

        elif project_info["type"] == "ios" and lang.lower() == "swift":
            # iOS 项目：保存到项目根目录或 generated 文件夹
            save_dir = work_dir / "generated"

        elif project_info["type"] == "web":
            # Web 项目：保存到 src 目录
            if (work_dir / "src").exists():
                save_dir = work_dir / "src"

        # 确保目录存在
        save_dir.mkdir(parents=True, exist_ok=True)

        # 确定文件扩展名
        ext_map = {
            "kotlin": "kt", "java": "java", "python": "py", "swift": "swift",
            "javascript": "js", "typescript": "ts", "go": "go", "rust": "rs",
            "c": "c", "cpp": "cpp", "csharp": "cs", "ruby": "rb",
            "php": "php", "scala": "scala", "bash": "sh", "shell": "sh",
            "json": "json", "xml": "xml", "html": "html", "css": "css",
            "sql": "sql", "markdown": "md", "yaml": "yaml", "yml": "yaml"
        }
        ext = ext_map.get(lang.lower(), lang if lang else "txt")

        # 生成文件名
        filename = f"generated_{timestamp}_{i+1}.{ext}"
        filepath = save_dir / filename

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        saved_files.append(str(filepath.relative_to(work_dir)) if filepath.is_relative_to(work_dir) else str(filepath))

    return saved_files


def call_local_model(model_id: str, prompt: str, max_tokens: int = 4096, temp: float = 0.7, model_alias: str = None) -> str:
    """调用本地模型（自动选择 MLX 或 llama.cpp 后端）"""
    from lib.backends import detect_backend, get_backend

    backend_type = detect_backend()
    backend = get_backend()

    # 确定模型 ID
    if model_alias and ":" in model_id:
        # 格式: owner/model:file.gguf -> 提取文件名作为模型别名
        pass

    success, output, metadata = backend.execute_text(
        model_id=model_id,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temp
    )

    if not success:
        raise RuntimeError(f"模型执行失败: {output}")

    return output


# 保留旧函数名兼容
def call_mlx_model(model_id: str, prompt: str, max_tokens: int = 4096, temp: float = 0.7) -> str:
    """调用模型（兼容旧接口）"""
    return call_local_model(model_id, prompt, max_tokens, temp)


def call_vl_model(model_id: str, image_path: str, prompt: str, max_tokens: int = 4096) -> str:
    """调用视觉模型（自动选择后端）"""
    from lib.backends import detect_backend, get_backend

    backend_type = detect_backend()
    backend = get_backend()

    # 确定视觉模型
    # 如果 model_id 不包含视觉模型信息，使用默认的
    if ":" not in model_id:
        # 尝试从配置获取视觉模型
        model_id = "vl"  # 使用别名

    success, output, metadata = backend.execute_vision(
        model_id=model_id,
        image_path=image_path,
        prompt=prompt,
        max_tokens=max_tokens
    )

    if not success:
        # 如果失败，尝试使用 MCP 路由的视觉检测
        try:
            from lib.mcp_router import vl_detect_element
            result = vl_detect_element(image_path, prompt)
            if result:
                return result.get("description", output)
        except:
            pass
        raise RuntimeError(f"视觉模型执行失败: {output}")

    return output


def show_help():
    """显示详细的中文帮助信息"""
    help_text = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    Local Commander - 本地模型指挥官                           ║
║                         让你拥有一个本地 AI 团队                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

📚 使用方法: /local [选项] [任务描述]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 可用模型
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  别名        模型                      用途                    内存
  ─────────────────────────────────────────────────────────────────────
  coder   Qwen2.5-Coder-14B-4bit   代码生成、审查、Debug       8GB
  vl      Qwen2.5-VL-7B-4bit       图像分析、UI验证、OCR        5GB
  35b     Qwen3.5-35B-MoE-4bit     复杂推理、架构设计、深度分析  18GB
  4b      Qwen3-4B-GPT5-Distill    快速对话、简单代码、代码片段  3.5GB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 基本命令
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /local <任务>                      执行任务（自动选择模型）
                                     示例: /local 写一个 Kotlin 扩展函数

  /local --model <模型> <任务>       指定模型执行任务
                                     示例: /local --model coder 帮我写个 Swift 类

  /local --smart <任务>              智能模式（带项目上下文）
                                     自动分析项目结构，生成更精准的代码

  /local --image <路径> <任务>       图像分析
                                     示例: /local --image ~/screenshot.png 分析这个UI

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 系统诊断
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /local --validate                  验证模型配置是否正确
  /local --models                    列出所有可用模型
  /local --system-info               显示系统信息（内存、芯片等）
  /local --benchmark                 对模型进行基准测试
  /local --optimize                  优化配置并验证
  /local --status                    查看当前会话状态

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 项目分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /local --analyze                   分析当前项目结构
  /local --analyze --scan-depth <深度>
                                     指定扫描深度:
                                       light  - 轻量扫描（最多50个文件）
                                       normal - 标准扫描（最多200个文件，默认）
                                       deep   - 深度扫描（最多1000个文件）
  /local --find <符号名>             查找项目中的符号（类、函数等）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 测试功能
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /local --test                      运行自动化测试（自动检测项目类型）

  /local --test --test-type <类型>   指定测试类型:
                                       Android: espresso, uiautomator, appium
                                       iOS:     xctest, xcuitest
                                       Web:     playwright, selenium, cypress

  /local --smart --test <任务>       智能模式 + 测试（生成代码后自动测试）

  /local --coverage                  分析代码覆盖率

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 AI 知识库
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /local --kb-add <内容>             添加知识点到知识库
                                     示例: /local --kb-add "SwiftUI 状态管理最佳实践"

  /local --kb-search <查询>          语义搜索知识库
                                     示例: /local --kb-search "如何处理异步任务"

  /local --kb-list                   列出所有知识点
  /local --kb-stats                  显示知识库统计信息
  /local --kb-delete <ID>            删除指定知识点

  知识点选项:
    --category <分类>                分类: coding, architecture, debugging, tools, concepts
    --tags <标签>                    标签（逗号分隔）: python,async,最佳实践
    --importance <数值>              重要程度: 0-1（默认0.5）
    --top-k <数量>                   搜索返回数量（默认5）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 自动路由关键词
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  包含以下关键词会自动路由到对应模型:

  coder:  代码、编程、Kotlin、Swift、函数、类、实现、写、生成、bug、debug
  vl:     图片、截图、图像、UI、界面、分析图、OCR、看
  27b:    架构、设计、方案、分析、评估、解释、为什么
  7b:     你好、hello、hi、谢谢、快速、简单

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️  高级选项
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  --max-tokens <数量>                最大生成 token 数（默认 4096）
  --max-context <数量>               最大上下文长度（默认 8192）
  --timeout <秒>                     模型调用超时时间（默认 600秒）
  --no-save                          不保存生成的代码到文件
  --output <路径>                    指定输出目录

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📖 示例
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /local 你好                                    # 快速问答
  /local 写一个 Kotlin 扩展函数                   # 代码生成
  /local --model 27b 分析这个架构设计             # 复杂推理
  /local --image screenshot.png 分析这个UI        # 图像分析
  /local --smart 实现用户登录功能                 # 智能模式
  /local --test --test-type espresso             # 运行测试
  /local --analyze --scan-depth deep             # 深度分析项目
  /local --kb-add "知识点内容" --category coding  # 添加知识

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 提示
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • 首次使用会自动下载模型到 ~/.cache/huggingface/hub/
  • 使用 --smart 模式可获得更精准的代码生成
  • 粘贴图片时自动调用 VL 模型分析
  • 知识库存储在 ~/.claude/knowledge_chroma/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    print(help_text)


def main():
    # 检查是否请求帮助
    if '--help' in sys.argv or '-h' in sys.argv:
        show_help()
        return

    parser = argparse.ArgumentParser(description='Local Commander - 本地模型指挥官')
    parser.add_argument('task', nargs='*', help='任务描述')
    parser.add_argument('--model', '-m', help='指定模型')
    parser.add_argument('--image', '-i', help='图片路径')
    parser.add_argument('--analyze', action='store_true', help='分析当前项目')
    parser.add_argument('--test', action='store_true', help='运行自动化测试 (Android/iOS/Web)')
    parser.add_argument('--test-type', type=str, default='auto', help='测试类型 (auto, espresso, uiautomator, xctest, xcuitest, playwright, selenium)')
    parser.add_argument('--test-dir', type=str, help='测试目录路径 (Web)')
    parser.add_argument('--apk-path', type=str, help='APK 路径 (Android)')
    parser.add_argument('--app-bundle', type=str, help='App Bundle 路径 (iOS)')
    parser.add_argument('--max-tokens', type=int, default=4096, help='最大 token 数 (默认 4096, --smart 模式默认 8192)')
    parser.add_argument('--no-save', action='store_true', help='不保存代码到文件')
    parser.add_argument('--output', '-o', help='指定输出路径')
    parser.add_argument('--find', type=str, help='查找符号或文件')
    parser.add_argument('--smart', action='store_true', help='智能模式（带项目上下文）')
    parser.add_argument('--status', action='store_true', help='查看会话状态')

    # 添加增强功能的参数
    parser.add_argument('--validate', action='store_true', help='验证模型配置')
    parser.add_argument('--benchmark', action='store_true', help='对模型进行基准测试')
    parser.add_argument('--models', action='store_true', help='列出可用模型')
    parser.add_argument('--system-info', action='store_true', help='显示系统信息')
    parser.add_argument('--optimize', action='store_true', help='优化配置')
    parser.add_argument('--test-target', type=str, help='指定测试目标 (Android/iOS)')
    parser.add_argument('--test-class', type=str, help='指定测试类 (Android)')
    parser.add_argument('--test-device', type=str, help='指定测试设备')
    # 添加覆盖率分析参数
    parser.add_argument('--coverage', action='store_true', help='分析代码覆盖率')
    parser.add_argument('--coverage-platform', type=str, default='auto', help='指定覆盖率分析平台 (auto, android, ios, web)')
    parser.add_argument('--coverage-variant', type=str, default='debug', help='Android 构建变体 (Android)')
    parser.add_argument('--coverage-scheme', type=str, help='iOS scheme 名称 (iOS)')
    parser.add_argument('--coverage-destination', type=str, help='iOS 测试目标 (iOS)')
    parser.add_argument('--coverage-test-command', type=str, help='Web 测试命令 (Web)')
    parser.add_argument('--coverage-dir', type=str, help='覆盖率报告目录 (Web)')
    parser.add_argument('--scan-depth', type=str, default='normal', choices=['light', 'normal', 'deep'], help='项目扫描深度 (默认: normal)')
    parser.add_argument('--timeout', type=int, default=600, help='模型调用超时时间 (秒)')
    parser.add_argument('--max-context', type=int, default=8192, help='最大上下文长度')

    # Embedding 相关参数
    parser.add_argument('--embed', action='store_true', help='生成文本向量 (使用 BGE-M3)')
    parser.add_argument('--embed-backend', type=str, default='huggingface', choices=['auto', 'ollama', 'huggingface'], help='Embedding 后端')
    parser.add_argument('--embed-model', type=str, default='bge-m3', help='Embedding 模型名称')

    # 知识库相关参数
    parser.add_argument('--kb-add', action='store_true', help='添加知识点到知识库')
    parser.add_argument('--kb-search', type=str, help='搜索知识库')
    parser.add_argument('--kb-list', action='store_true', help='列出知识点')
    parser.add_argument('--kb-stats', action='store_true', help='显示知识库统计')
    parser.add_argument('--kb-delete', type=str, help='删除知识点 (指定 ID)')
    parser.add_argument('--kb-export', type=str, help='导出知识库到文件')
    parser.add_argument('--kb-import', type=str, help='从文件导入知识库')
    parser.add_argument('--category', type=str, default='general', help='知识点分类')
    parser.add_argument('--tags', type=str, help='知识点标签 (逗号分隔)')
    parser.add_argument('--importance', type=float, default=0.5, help='知识点重要程度 (0-1)')
    parser.add_argument('--top-k', type=int, default=5, help='搜索返回数量')

    args = parser.parse_args()

    # 获取当前工作目录
    work_dir = Path.cwd()

    # 处理增强功能
    if args.validate:
        print("🔍 验证模型配置...")
        config_validation = validate_model_configuration()
        print(json.dumps(config_validation, indent=2, ensure_ascii=False))
        return

    if args.models:
        print("📦 可用模型列表:")
        models = list_available_models()
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model}")
        if not models:
            print("  未找到任何模型")
        return

    if args.benchmark:
        print("⚡ 对模型进行基准测试...")
        config_validation = validate_model_configuration()
        if config_validation["recommended_model"]:
            result = benchmark_model(config_validation["recommended_model"])
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("❌ 未找到可用模型进行基准测试")
        return

    if args.system_info:
        print("💻 系统信息:")
        sys_info = get_system_info()
        print(json.dumps(sys_info, indent=2, ensure_ascii=False))
        return

    if args.optimize:
        print("⚙️  优化配置...")
        config_path = setup_optimized_config()
        print(f"✅ 优化配置已保存至: {config_path}")

        # 同时执行验证
        config_validation = validate_model_configuration()
        print("\n📋 配置验证结果:")
        print(json.dumps(config_validation, indent=2, ensure_ascii=False))
        return

    # 分析项目
    if args.analyze:
        from lib.analyzer import get_analyzer
        from lib.file_ops import get_file_ops

        analyzer = get_analyzer()
        analyzer.set_project(work_dir)

        # 根据扫描深度优化扫描
        scan_strategy = optimize_project_scanning(args.scan_depth)
        print(f"🔍 扫描深度: {args.scan_depth} (文件限制: {scan_strategy['max_files']})")

        result = analyzer.scan_project()
        print(f"\n📊 项目分析结果")
        print(f"   类型: {result.get('project_type', 'unknown')}")
        print(f"   文件: {result.get('files', 0)} 个")
        print(f"   符号: {result.get('symbols', 0)} 个")
        print(f"   类: {result.get('classes', 0)} 个")
        print(f"   函数: {result.get('functions', 0)} 个")
        return

    # 查找符号
    if args.find:
        from lib.analyzer import get_analyzer

        analyzer = get_analyzer()
        analyzer.set_project(work_dir)
        analyzer.scan_project()

        symbols = analyzer.find_symbol(args.find)
        if symbols:
            print(f"\n🔍 找到 {len(symbols)} 个匹配:")
            for s in symbols[:10]:
                print(f"   {s.name} ({s.type})")
                print(f"      文件: {s.file_path}:{s.line_start}")
                if s.parent:
                    print(f"      父级: {s.parent}")
        else:
            print(f"未找到: {args.find}")
        return

    # 查看状态
    if args.status:
        sm = get_session_manager()
        session = sm.get_session()
        project_info = detect_project_type(work_dir)

        print(f"工作目录: {work_dir}")
        print(f"项目类型: {project_info['type']}")
        if project_info['source_dir']:
            print(f"源码目录: {project_info['source_dir']}")

        if session:
            print(f"会话状态: {'活跃' if session.get('active') else '非活跃'}")
            print(f"任务数: {session.get('task_count', 0)}")
        else:
            print("无活跃会话")
        return

    # Embedding 功能
    if args.embed:
        print(f"🔮 生成向量 (模型: {args.embed_model}, 后端: {args.embed_backend})...")
        if not args.task:
            print("请提供要编码的文本，例如: /local --embed '你好世界'")
            return

        text = ' '.join(args.task)
        embedder = get_embedder(backend=args.embed_backend, model=args.embed_model)
        embeddings = embedder.encode([text])

        print(f"向量维度: {embeddings.shape[1]}")
        print(f"向量 (前10维): {embeddings[0][:10].tolist()}")
        return

    # ====== AI 知识库功能 ======
    kb = get_knowledge_base()

    # 添加知识点
    if args.kb_add:
        if not args.task:
            print("请提供知识点内容")
            return

        text = ' '.join(args.task)
        tags = args.tags.split(',') if args.tags else []

        item = kb.add(
            text=text,
            category=args.category,
            tags=tags,
            importance=args.importance
        )
        print(f"✅ 已添加知识点")
        print(f"   ID: {item['id']}")
        print(f"   分类: {item['category']}")
        print(f"   标签: {item['tags']}")
        print(f"   摘要: {item['summary']}")
        return

    # 搜索知识库
    if args.kb_search:
        query = args.kb_search
        tags = args.tags.split(',') if args.tags else []

        print(f"🔍 搜索知识库: {query}")
        results = kb.search(
            query=query,
            top_k=args.top_k,
            category=args.category if args.category != 'general' else None,
            tags=tags if tags else None
        )

        if not results:
            print("未找到相关知识点")
            return

        print(f"\n找到 {len(results)} 个相关知识点:")
        for i, r in enumerate(results, 1):
            print(f"\n--- [{r['id']}] 相似度: {r['score']:.4f} ---")
            print(f"分类: {r['category']} | 标签: {r['tags']}")
            print(f"内容: {r['text'][:200]}{'...' if len(r['text']) > 200 else ''}")
        return

    # 列出知识点
    if args.kb_list:
        tags = args.tags.split(',') if args.tags else []
        items = kb.list(
            category=args.category if args.category != 'general' else None,
            tags=tags if tags else None,
            limit=args.top_k
        )

        if not items:
            print("知识库为空")
            return

        print(f"📚 知识点列表 (共 {len(items)} 条):")
        for item in items:
            print(f"\n[{item['id']}] {item['summary']}")
            print(f"   分类: {item['category']} | 标签: {item['tags']} | 重要度: {item['importance']}")
        return

    # 知识库统计
    if args.kb_stats:
        stats = kb.stats()
        print("📊 知识库统计:")
        print(f"   总数: {stats['total']} 条")
        print(f"   存储大小: {stats['storage_size_mb']:.2f} MB")
        print(f"   分类分布: {stats['categories']}")
        print(f"   热门标签: {stats['top_tags']}")
        return

    # 删除知识点
    if args.kb_delete:
        if kb.delete(args.kb_delete):
            print(f"✅ 已删除知识点: {args.kb_delete}")
        else:
            print(f"❌ 未找到知识点: {args.kb_delete}")
        return

    # 导出知识库
    if args.kb_export:
        kb.export(args.kb_export)
        print(f"✅ 已导出知识库到: {args.kb_export}")
        return

    # 导入知识库
    if args.kb_import:
        kb.import_from(args.kb_import)
        print(f"✅ 已导入知识库: {args.kb_import}")
        print(f"   当前总数: {len(kb.knowledge)} 条")
        return

    # 运行覆盖率分析
    if args.coverage:
        from lib.testers import get_test_executor

        executor = get_test_executor()
        coverage_kwargs = {}

        if args.coverage_variant:
            coverage_kwargs['variant'] = args.coverage_variant
        if args.coverage_scheme:
            coverage_kwargs['scheme'] = args.coverage_scheme
        if args.coverage_destination:
            coverage_kwargs['destination'] = args.coverage_destination
        if args.coverage_test_command:
            coverage_kwargs['test_command'] = args.coverage_test_command
        if args.coverage_dir:
            coverage_kwargs['coverage_dir'] = args.coverage_dir

        coverage_result = executor.run_coverage_analysis(
            str(work_dir),
            platform=args.coverage_platform,
            **coverage_kwargs
        )

        if 'error' not in coverage_result:
            print(f"✅ 代码覆盖率分析完成:")
            print(f"   平台: {coverage_result.get('platform', 'unknown')}")
            print(f"   类型: {coverage_result.get('type', 'unknown')}")
            print(f"   报告路径: {coverage_result.get('report_path', 'N/A')}")

            coverage_data = coverage_result.get('coverage', {})
            if 'overall_coverage' in coverage_data:
                if isinstance(coverage_data['overall_coverage'], dict):
                    # For JaCoCo format
                    for coverage_type, data in coverage_data['overall_coverage'].items():
                        print(f"   {coverage_type}: {data['percentage']}% ({data['covered']}/{data['total']})")
                else:
                    # For other formats
                    print(f"   整体覆盖率: {coverage_data['overall_coverage']}%")
        else:
            print(f"❌ 覆盖率分析失败: {coverage_result['error']}")
        return

    # 运行自动化测试
    if args.test:
        if args.task:
            task = ' '.join(args.task)
            print(f"正在为任务 '{task}' 运行自动化测试...")

        from lib.executor import get_executor

        executor = get_executor()
        test_kwargs = {}
        if args.test_dir:
            test_kwargs['test_dir'] = args.test_dir
        if args.apk_path:
            test_kwargs['apk_path'] = args.apk_path
        if args.app_bundle:
            test_kwargs['app_bundle'] = args.app_bundle
        # 添加新参数支持
        if args.test_target:
            test_kwargs['test_target'] = args.test_target
        if args.test_class:
            test_kwargs['test_class'] = args.test_class
        if args.test_device:
            test_kwargs['test_device'] = args.test_device
        # 增强测试框架参数
        if hasattr(args, 'package_name') and args.package_name:
            test_kwargs['package_name'] = args.package_name
        if hasattr(args, 'test_runner') and args.test_runner:
            test_kwargs['test_runner'] = args.test_runner
        if hasattr(args, 'project_path') and args.project_path:
            test_kwargs['project_path'] = args.project_path
        if hasattr(args, 'scheme') and args.scheme:
            test_kwargs['scheme'] = args.scheme
        if hasattr(args, 'destination') and args.destination:
            test_kwargs['destination'] = args.destination
        if hasattr(args, 'config_file') and args.config_file:
            test_kwargs['config_file'] = args.config_file
        if hasattr(args, 'threshold') and args.threshold:
            test_kwargs['threshold'] = args.threshold
        if hasattr(args, 'test_pattern') and args.test_pattern:
            test_kwargs['test_pattern'] = args.test_pattern

        test_result = executor.run_automated_tests(str(work_dir), args.test_type, **test_kwargs)

        if 'error' not in test_result:
            print(f"✅ 自动化测试执行完成:")
            print(f"   平台: {test_result.get('platform', 'unknown')}")
            print(f"   类型: {test_result.get('type', 'unknown')}")
            print(f"   总计: {test_result.get('total', 0)}, 通过: {test_result.get('passed', 0)}, 失败: {test_result.get('failed', 0)}")
            if test_result.get('report_path'):
                print(f"   报告: {test_result['report_path']}")
        else:
            print(f"❌ 测试执行失败: {test_result['error']}")
        return

    # 执行任务
    if not args.task:
        print("请提供任务描述，例如: /local 你好")
        return

    task = ' '.join(args.task)

    # 路由模型
    router = get_router()
    if args.model:
        model = router._get_model_by_alias(args.model)
    else:
        model = router.route(task)

    model_id = model['id']
    model_alias = model['alias']

    print(f"[{model_alias}]", end=" ", flush=True)

    # 启动会话
    sm = get_session_manager()
    sm.start_session()

    try:
        # 智能模式：带项目上下文
        if args.smart:
            from lib.executor import get_executor
            from lib.analyzer import get_analyzer

            executor = get_executor()

            if args.test:
                # 执行任务并运行自动化测试
                success, output, meta = executor.execute_with_testing(
                    model_id, task, work_dir, args.max_context
                )
            else:
                # 正常执行带上下文的任务
                success, output, meta = executor.execute_with_context(
                    model_id, task, work_dir, args.max_context
                )

            print()
            print(output)
            if 'target_file' in meta:
                print(f"\n📁 修改文件: {meta['target_file']}")
            if 'test_results' in meta:
                test_results = meta['test_results']
                if test_results.get('failed', 0) > 0:
                    print(f"\n⚠️  测试发现 {test_results.get('failed', 0)} 个失败")
                else:
                    print(f"\n✅ 所有 {test_results.get('passed', 0)} 个测试通过")
            return

        # 判断是否是视觉模型
        if args.image or 'vl' in model_alias.lower():
            if args.image:
                output = call_vl_model(model_id, args.image, task, args.max_tokens)
            else:
                output = "错误：视觉模型需要提供图片路径 (--image)"
                print(output)
                return
        else:
            output = call_mlx_model(model_id, task, args.max_tokens)

        # 记录历史
        sm.add_history(task, model_alias, output, True)

        # 提取代码块
        code_blocks = extract_code_blocks(output)
        saved_files = []

        # 保存代码
        if code_blocks and not args.no_save:
            project_info = detect_project_type(work_dir)

            if args.output:
                # 用户指定输出路径
                output_path = Path(args.output)
                output_path.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                for i, (lang, code) in enumerate(code_blocks):
                    ext_map = {"kotlin": "kt", "java": "java", "python": "py", "swift": "swift",
                               "javascript": "js", "typescript": "ts"}
                    ext = ext_map.get(lang.lower(), lang if lang else "txt")
                    filepath = output_path / f"generated_{timestamp}_{i+1}.{ext}"
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(code)
                    saved_files.append(str(filepath))
            else:
                # 智能保存到当前项目
                saved_files = save_code_to_project(code_blocks, work_dir, project_info)

        # 输出结果
        print()
        print(output)

        # 显示保存的文件
        if saved_files:
            print("\n---")
            print("📁 已保存:")
            for f in saved_files:
                print(f"   {f}")

    except Exception as e:
        sm.add_history(task, model_alias, str(e), False)
        print(f"\n❌ 执行失败: {e}")


if __name__ == '__main__':
    main()