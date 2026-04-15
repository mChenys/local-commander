"""
MLX 后端 - Apple Silicon Mac 专用
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from .base import Backend, BackendInfo


class MLXBackend(Backend):
    """MLX 模型后端 (Apple Silicon)"""

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._hf_cache = Path.home() / ".cache" / "huggingface" / "hub"

    def get_info(self) -> BackendInfo:
        """获取 MLX 后端信息"""
        if self._info:
            return self._info

        import platform

        system = platform.system()
        machine = platform.machine()

        # 检查是否为 Apple Silicon
        is_apple_silicon = system == "Darwin" and machine == "arm64"

        # 检查 MLX 是否安装
        mlx_installed = False
        mlx_version = ""
        try:
            import mlx
            mlx_installed = True
            mlx_version = getattr(mlx, "__version__", "unknown")
        except ImportError:
            pass

        # 检查命令行工具
        mlx_lm_available = shutil.which("mlx_lm.generate") is not None
        mlx_vlm_available = shutil.which("mlx_vlm.generate") is not None

        is_available = is_apple_silicon and mlx_installed

        self._info = BackendInfo(
            name="MLX",
            version=mlx_version,
            platform=f"{system}/{machine}",
            supported_features=[
                "text_generation",
                "vision" if mlx_vlm_available else None,
                "metal_acceleration"
            ],
            is_available=is_available,
            error_message=None if is_available else
                "MLX 仅支持 Apple Silicon Mac" if not is_apple_silicon else
                "请安装 MLX: pip install mlx mlx-lm mlx-vlm"
        )

        return self._info

    def execute(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """执行 MLX 文本模型"""
        formatted_prompt = self.format_prompt(prompt, model_id)

        cmd = [
            "mlx_lm.generate",
            "--model", model_id,
            "--prompt", formatted_prompt,
            "--max-tokens", str(max_tokens),
            "--temp", str(temperature)
        ]

        metadata = {
            "backend": "mlx",
            "model": model_id,
            "type": "text"
        }

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=kwargs.get("timeout", 600)
            )

            if result.returncode != 0:
                return False, result.stderr, metadata

            output = self.parse_output(result.stdout)
            return True, output, metadata

        except subprocess.TimeoutExpired:
            return False, "执行超时", metadata
        except Exception as e:
            return False, str(e), metadata

    def execute_vision(
        self,
        model_id: str,
        prompt: str,
        image_path: str,
        max_tokens: int = 4096,
        **kwargs
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """执行 MLX 视觉模型"""
        cmd = [
            "mlx_vlm.generate",
            "--model", model_id,
            "--prompt", prompt,
            "--image", image_path,
            "--max-tokens", str(max_tokens)
        ]

        metadata = {
            "backend": "mlx",
            "model": model_id,
            "image": image_path,
            "type": "vision"
        }

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=kwargs.get("timeout", 600)
            )

            if result.returncode != 0:
                return False, result.stderr, metadata

            output = self.parse_output(result.stdout)
            return True, output, metadata

        except subprocess.TimeoutExpired:
            return False, "执行超时", metadata
        except Exception as e:
            return False, str(e), metadata

    def is_model_available(self, model_id: str) -> bool:
        """检查 MLX 模型是否可用"""
        # 检查本地缓存
        if model_id.startswith("/"):
            return Path(model_id).exists()

        # 检查 HuggingFace 缓存
        cache_name = model_id.replace("/", "--")
        cache_path = self._hf_cache / f"models--{cache_name}"
        return cache_path.exists()

    def list_models(self) -> List[Dict[str, Any]]:
        """列出本地缓存的 MLX 模型"""
        models = []

        if not self._hf_cache.exists():
            return models

        for model_dir in self._hf_cache.iterdir():
            if model_dir.is_dir() and model_dir.name.startswith("models--"):
                # 提取模型名
                model_name = model_dir.name.replace("models--", "").replace("--", "/")
                models.append({
                    "id": model_name,
                    "path": str(model_dir),
                    "backend": "mlx"
                })

        return models
