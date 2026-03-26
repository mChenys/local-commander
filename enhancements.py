"""
Local Commander 增强功能模块
"""
import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import subprocess
import time


def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    import platform
    return {
        "os": platform.system(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cwd": str(Path.cwd()),
        "available_models": list_available_models()
    }


def list_available_models() -> List[str]:
    """列出可用的本地模型"""
    models_dir = Path.home() / ".mlx/models"
    if models_dir.exists():
        return [d.name for d in models_dir.iterdir() if d.is_dir()]
    else:
        # 尝试其他常见的模型目录
        alt_dirs = [
            Path("/opt/mlx/models"),
            Path("./models"),
            Path("~/mlx_models").expanduser()
        ]

        for models_dir in alt_dirs:
            if models_dir.exists():
                return [d.name for d in models_dir.iterdir() if d.is_dir()]

    return []


def benchmark_model(model_id: str, test_prompt: str = "你好") -> Dict[str, Any]:
    """对模型进行基准测试"""
    start_time = time.time()

    try:
        result = subprocess.run([
            'mlx_lm.generate',
            '--model', model_id,
            '--prompt', f'You are a helpful assistant. 回复要简洁专业。用户问题：{test_prompt}',
            '--max-tokens', '128',
            '--temp', '0.1'
        ], capture_output=True, text=True, timeout=30)

        end_time = time.time()

        if result.returncode == 0:
            output = result.stdout
            # 解析输出
            lines = output.split('\n')
            in_content = False
            content_lines = []
            for line in lines:
                if '==========' in line:
                    in_content = not in_content
                    continue
                if in_content:
                    content_lines.append(line)

            response = '\n'.join(content_lines).strip()

            return {
                "success": True,
                "model": model_id,
                "response": response,
                "latency": round(end_time - start_time, 2),
                "return_code": result.returncode
            }
        else:
            return {
                "success": False,
                "model": model_id,
                "error": result.stderr,
                "latency": round(end_time - start_time, 2),
                "return_code": result.returncode
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "model": model_id,
            "error": "模型响应超时",
            "latency": 30.0,
            "return_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "model": model_id,
            "error": str(e),
            "latency": round(time.time() - start_time, 2),
            "return_code": -1
        }


def validate_model_configuration() -> Dict[str, Any]:
    """验证模型配置"""
    results = {
        "mlx_installed": False,
        "models_available": [],
        "default_model_works": False,
        "recommended_model": None
    }

    # 检查 MLX 是否安装
    try:
        import mlx
        import mlx_lm
        results["mlx_installed"] = True
    except ImportError:
        results["mlx_installed"] = False

    # 检查可用模型
    available_models = list_available_models()
    results["models_available"] = available_models

    # 测试默认模型
    if available_models:
        # 尝试一些常用的模型名称
        priority_models = [
            "Qwen3.5-27B-Instruct-4bit",
            "Qwen2.5-Coder-14B-Instruct-4bit",
            "Qwen2.5-VL-7B-Instruct-4bit",
            "Qwen2.5-7B-Instruct-4bit"
        ]

        # 检查优先级模型是否存在
        for model in priority_models:
            if model in available_models:
                results["recommended_model"] = model
                test_result = benchmark_model(model)
                results["default_model_works"] = test_result["success"]
                break
        else:
            # 如果没有找到推荐模型，则测试第一个可用模型
            if available_models:
                results["recommended_model"] = available_models[0]
                test_result = benchmark_model(available_models[0])
                results["default_model_works"] = test_result["success"]

    return results


def create_model_alias_config() -> Dict[str, str]:
    """创建模型别名配置"""
    aliases = {
        "coder": "Qwen2.5-Coder-14B-Instruct-4bit",
        "vl": "Qwen2.5-VL-7B-Instruct-4bit",
        "27b": "Qwen3.5-27B-Instruct-4bit",
        "7b": "Qwen2.5-7B-Instruct-4bit"
    }

    # 检查实际可用的模型并调整别名
    available = list_available_models()
    adjusted_aliases = {}

    for alias, default_model in aliases.items():
        # 检查默认模型是否存在，否则找一个类似的
        if default_model in available:
            adjusted_aliases[alias] = default_model
        else:
            # 找一个相似的模型
            similar = [m for m in available if alias.lower() in m.lower()]
            if similar:
                adjusted_aliases[alias] = similar[0]
            else:
                # 找任何包含类似关键词的模型
                if alias == "coder":
                    similar = [m for m in available if "coder" in m.lower() or "code" in m.lower()]
                elif alias == "vl":
                    similar = [m for m in available if "vl" in m.lower() or "vision" in m.lower()]
                elif alias == "27b":
                    similar = [m for m in available if "27b" in m.lower() or "3.5" in m.lower()]
                elif alias == "7b":
                    similar = [m for m in available if "7b" in m.lower() or "2.5" in m.lower()]

                if similar:
                    adjusted_aliases[alias] = similar[0]
                else:
                    # 如果真的找不到匹配的，就用第一个可用的
                    if available:
                        adjusted_aliases[alias] = available[0]

    return adjusted_aliases


def optimize_cli_arguments(parser):
    """优化 CLI 参数"""
    # 添加新的功能参数
    parser.add_argument('--validate', action='store_true', help='验证模型配置')
    parser.add_argument('--benchmark', action='store_true', help='对模型进行基准测试')
    parser.add_argument('--models', action='store_true', help='列出可用模型')
    parser.add_argument('--system-info', action='store_true', help='显示系统信息')
    parser.add_argument('--optimize', action='store_true', help='优化配置')

    # 添加更多测试类型
    parser.add_argument('--test-target', type=str, help='指定测试目标 (Android/iOS)')
    parser.add_argument('--test-class', type=str, help='指定测试类 (Android)')
    parser.add_argument('--test-device', type=str, help='指定测试设备')

    # 项目分析增强
    parser.add_argument('--scan-depth', type=str, default='normal',
                       choices=['light', 'normal', 'deep'],
                       help='项目扫描深度 (默认: normal)')

    # 性能参数
    parser.add_argument('--timeout', type=int, default=600, help='模型调用超时时间 (秒)')
    parser.add_argument('--max-context', type=int, default=8192, help='最大上下文长度')

    return parser


def optimize_project_scanning(scan_depth: str = 'normal'):
    """优化项目扫描策略"""
    strategies = {
        'light': {
            'max_files': 50,
            'max_file_size': 10000,  # 10KB
            'max_depth': 2,
            'scan_config_files': True,
            'scan_code_symbols': False
        },
        'normal': {
            'max_files': 200,
            'max_file_size': 50000,  # 50KB
            'max_depth': 4,
            'scan_config_files': True,
            'scan_code_symbols': True
        },
        'deep': {
            'max_files': 1000,
            'max_file_size': 100000,  # 100KB
            'max_depth': 8,
            'scan_config_files': True,
            'scan_code_symbols': True
        }
    }

    return strategies.get(scan_depth, strategies['normal'])


def generate_performance_report():
    """生成性能报告"""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": get_system_info(),
        "configuration": validate_model_configuration(),
        "recommendations": []
    }

    # 根据配置生成建议
    config = report["configuration"]
    if not config["mlx_installed"]:
        report["recommendations"].append("MLX 未安装，请运行: pip install mlx mlx-lm")

    if not config["models_available"]:
        report["recommendations"].append("未检测到本地模型，请下载 MLX 模型")
    elif not config["default_model_works"]:
        report["recommendations"].append(f"推荐模型 {config['recommended_model']} 无法正常工作")

    return report


def setup_optimized_config():
    """设置优化的配置"""
    config_dir = Path.home() / ".mlx" / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)

    # 创建模型路由配置
    router_config = {
        "aliases": create_model_alias_config(),
        "routing_rules": {
            "keywords": {
                "code|coder|implement|write|function|class|method|debug|fix": "coder",
                "image|picture|screenshot|visual|ui|screen|photo": "vl",
                "arch|design|plan|analyze|strategy|evaluate": "27b",
                "quick|simple|hi|hello|short": "7b"
            }
        }
    }

    config_file = config_dir / "router.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(router_config, f, indent=2, ensure_ascii=False)

    return config_file


if __name__ == "__main__":
    # 如果直接运行此脚本，显示系统信息
    print("=== Local Commander 增强功能测试 ===")
    print("\n系统信息:")
    sys_info = get_system_info()
    for key, value in sys_info.items():
        print(f"  {key}: {value}")

    print("\n模型配置验证:")
    validation = validate_model_configuration()
    for key, value in validation.items():
        print(f"  {key}: {value}")

    if validation["models_available"]:
        print(f"\n推荐模型: {validation['recommended_model']}")
        if validation["recommended_model"]:
            print(f"\n测试 {validation['recommended_model']} 性能:")
            benchmark_result = benchmark_model(validation["recommended_model"])
            print(f"  成功: {benchmark_result['success']}")
            print(f"  延迟: {benchmark_result['latency']}s")
            if benchmark_result['success']:
                print(f"  响应: {benchmark_result['response'][:100]}...")

    print(f"\n优化配置已保存至: {setup_optimized_config()}")