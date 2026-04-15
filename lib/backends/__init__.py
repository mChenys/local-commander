"""
后端抽象层 - 支持 MLX 和 llama.cpp 双后端
"""

from .base import Backend, BackendInfo
from .mlx_backend import MLXBackend
from .llamacpp_backend import LlamaCppBackend

__all__ = [
    "Backend",
    "BackendInfo",
    "MLXBackend",
    "LlamaCppBackend",
    "get_backend",
    "detect_backend"
]


def detect_backend() -> str:
    """
    检测系统可用的后端

    Returns:
        "mlx" - Apple Silicon Mac
        "llamacpp" - Intel Mac / Linux / 其他
    """
    import platform
    import shutil

    system = platform.system()
    machine = platform.machine()

    # Apple Silicon Mac: 优先使用 MLX
    if system == "Darwin" and machine == "arm64":
        # 检查 MLX 是否安装
        try:
            import mlx
            return "mlx"
        except ImportError:
            pass

    # 其他情况: 使用 llama.cpp
    # 检查 llama-cli 是否安装
    if shutil.which("llama-cli") or shutil.which("main"):
        return "llamacpp"

    # 默认返回 llama.cpp (安装脚本会安装它)
    return "llamacpp"


def get_backend(config: dict = None) -> Backend:
    """
    获取当前系统可用的后端实例

    Args:
        config: 模型配置 (可选)

    Returns:
        Backend 实例
    """
    backend_type = detect_backend()

    if backend_type == "mlx":
        return MLXBackend(config)
    else:
        return LlamaCppBackend(config)
