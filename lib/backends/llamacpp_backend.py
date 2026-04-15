"""
llama.cpp 后端 - 支持 Intel Mac 和其他平台
"""

import subprocess
import shutil
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from .base import Backend, BackendInfo


class LlamaCppBackend(Backend):
    """llama.cpp 模型后端 (跨平台)"""

    # GGUF 模型推荐映射
    GGUF_MODEL_MAP = {
        # 文本模型
        "coder": {
            "hf_repo": "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
            "gguf_file": "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
            "memory_gb": 9,
            "use_cases": ["代码生成", "代码审查", "Bug诊断"]
        },
        "fast": {
            "hf_repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
            "gguf_file": "qwen2.5-7b-instruct-q4_k_m.gguf",
            "memory_gb": 5,
            "use_cases": ["快速对话", "简单代码"]
        },
        "reasoning": {
            "hf_repo": "Qwen/Qwen2.5-14B-Instruct-GGUF",
            "gguf_file": "qwen2.5-14b-instruct-q4_k_m.gguf",
            "memory_gb": 9,
            "use_cases": ["复杂推理", "架构设计"]
        },
        # 视觉模型
        "vl": {
            "hf_repo": "mobiuslabsgmbh/MiniCPM-V-2_6-gguf",
            "gguf_file": "MiniCPM-V-2_6-Q4_K_M.gguf",
            "mmproj_file": "mmproj-model-f16.gguf",
            "memory_gb": 5,
            "use_cases": ["图像分析", "UI验证", "OCR"]
        },
        "llava": {
            "hf_repo": "cjpais/llava-v1.6-mistral-7b-GGUF",
            "gguf_file": "llava-v1.6-mistral-7b.Q4_K_M.gguf",
            "mmproj_file": "llava-v1.6-mistral-7b-mmproj-Q4_K_M.gguf",
            "memory_gb": 5,
            "use_cases": ["图像分析", "视觉问答"]
        }
    }

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
        self._llama_cli = self._find_llama_cli()

    def _find_llama_cli(self) -> str:
        """查找 llama-cli 命令"""
        # 常见的 llama-cli 路径
        candidates = [
            "llama-cli",
            "llama",
            "main",
            "/usr/local/bin/llama-cli",
            "/opt/homebrew/bin/llama-cli",
            os.path.expanduser("~/.local/bin/llama-cli"),
        ]

        for cmd in candidates:
            if shutil.which(cmd):
                return cmd

        # 检查 llama.cpp 目录
        llama_cpp_dir = Path.home() / "llama.cpp"
        if llama_cpp_dir.exists():
            main_bin = llama_cpp_dir / "main"
            if main_bin.exists():
                return str(main_bin)

        return "llama-cli"  # 默认值，可能需要安装

    def get_info(self) -> BackendInfo:
        """获取 llama.cpp 后端信息"""
        if self._info:
            return self._info

        import platform

        system = platform.system()
        machine = platform.machine()

        # 检查 llama-cli 是否可用
        llama_available = shutil.which(self._llama_cli) is not None

        # 获取版本
        llama_version = ""
        if llama_available:
            try:
                result = subprocess.run(
                    [self._llama_cli, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # 解析版本
                if result.stdout:
                    llama_version = result.stdout.split("\n")[0].strip()
            except Exception:
                llama_version = "unknown"

        # 检测支持的特性
        features = ["text_generation", "gguf_models", "cpu_inference"]

        # 检查是否有 Metal 支持 (macOS)
        if system == "Darwin":
            features.append("metal_possible")

        # 检查是否有 CUDA 支持
        if shutil.which("nvidia-smi"):
            features.append("cuda_possible")

        self._info = BackendInfo(
            name="llama.cpp",
            version=llama_version,
            platform=f"{system}/{machine}",
            supported_features=features,
            is_available=llama_available,
            error_message=None if llama_available else
                "请安装 llama.cpp: brew install llama.cpp 或从 https://github.com/ggml-org/llama.cpp 编译"
        )

        return self._info

    def _get_model_path(self, model_key: str) -> Optional[str]:
        """
        获取 GGUF 模型的本地路径

        Args:
            model_key: 模型键名 (coder, vl, etc.)

        Returns:
            模型文件路径，如果不存在返回 None
        """
        model_info = self.GGUF_MODEL_MAP.get(model_key)
        if not model_info:
            return None

        hf_repo = model_info["hf_repo"]
        gguf_file = model_info["gguf_file"]

        # 检查 HuggingFace 缓存
        cache_name = hf_repo.replace("/", "--")
        cache_path = self._hf_cache / f"models--{cache_name}"

        if cache_path.exists():
            # 查找 GGUF 文件
            for blob_dir in cache_path.glob("blobs/*"):
                if blob_dir.is_file():
                    # 检查文件名
                    snapshots_dir = cache_path / "snapshots"
                    if snapshots_dir.exists():
                        for snapshot in snapshots_dir.iterdir():
                            gguf_path = snapshot / gguf_file
                            if gguf_path.exists():
                                return str(gguf_path)

        # 检查自定义路径
        if self.config:
            models = self.config.get("models", {})
            model_config = models.get(model_key, {})
            custom_path = model_config.get("path")
            if custom_path and Path(custom_path).exists():
                return custom_path

        return None

    def execute(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """使用 llama-cli 执行文本模型"""
        formatted_prompt = self.format_prompt(prompt, model_id)

        # 获取模型路径
        model_path = model_id
        if not Path(model_id).exists():
            # 可能是模型键名
            model_path = self._get_model_path(model_id)
            if not model_path:
                return False, f"模型不存在: {model_id}", {"backend": "llamacpp"}

        cmd = [
            self._llama_cli,
            "-m", model_path,
            "-p", formatted_prompt,
            "-n", str(max_tokens),
            "--temp", str(temperature),
            "-ngl", "0",  # 不使用 GPU layers (CPU 模式)
            "-c", "4096",  # 上下文长度
            "--no-display-prompt",  # 不显示输入提示
            "-r", "<|im_end|>",  # 停止词
            "-r", "<|eot_id|>",
            "-r", "</s>",
        ]

        metadata = {
            "backend": "llamacpp",
            "model": model_id,
            "model_path": model_path,
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

            # llama-cli 输出格式不同，直接提取内容
            output = self._parse_llama_output(result.stdout)
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
        """使用 llama-cli 执行视觉模型 (llava/minicpm-v)"""
        # 获取模型路径
        model_path = model_id
        mmproj_path = None

        if not Path(model_id).exists():
            # 可能是模型键名 (vl 或 llava)
            model_info = self.GGUF_MODEL_MAP.get(model_id)
            if not model_info:
                # 尝试其他视觉模型
                for key in ["vl", "llava"]:
                    path = self._get_model_path(key)
                    if path:
                        model_path = path
                        model_info = self.GGUF_MODEL_MAP[key]
                        break

            if model_info:
                # 获取 mmproj 文件
                mmproj_file = model_info.get("mmproj_file")
                if mmproj_file:
                    hf_repo = model_info["hf_repo"]
                    cache_name = hf_repo.replace("/", "--")
                    cache_path = self._hf_cache / f"models--{cache_name}"
                    if cache_path.exists():
                        snapshots_dir = cache_path / "snapshots"
                        if snapshots_dir.exists():
                            for snapshot in snapshots_dir.iterdir():
                                mmproj_candidate = snapshot / mmproj_file
                                if mmproj_candidate.exists():
                                    mmproj_path = str(mmproj_candidate)
                                    break

        if not model_path or not Path(model_path).exists():
            return False, f"视觉模型不存在: {model_id}", {"backend": "llamacpp"}

        if not mmproj_path:
            return False, f"mmproj 文件不存在，无法进行视觉推理", {"backend": "llamacpp"}

        cmd = [
            self._llama_cli,
            "-m", model_path,
            "--mmproj", mmproj_path,
            "--image", image_path,
            "-p", prompt,
            "-n", str(max_tokens),
            "--temp", "0.1",
            "-ngl", "0",
            "-c", "4096",
        ]

        metadata = {
            "backend": "llamacpp",
            "model": model_id,
            "model_path": model_path,
            "mmproj": mmproj_path,
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

            output = self._parse_llama_output(result.stdout)
            return True, output, metadata

        except subprocess.TimeoutExpired:
            return False, "执行超时", metadata
        except Exception as e:
            return False, str(e), metadata

    def _parse_llama_output(self, raw: str) -> str:
        """解析 llama-cli 输出"""
        # llama-cli 输出通常直接是生成的内容
        lines = raw.strip().split("\n")

        # 过滤掉一些日志信息
        content_lines = []
        skip_patterns = [
            "llama_model_loader:",
            "llama_init_from_model:",
            "llama_context:",
            "llama_new_context_with_model:",
            "llama_kv_cache",
            "llama_print_timings:",
            "system_info:",
            "load_image",
            "eval: ",
            "generate:",
        ]

        for line in lines:
            skip = False
            for pattern in skip_patterns:
                if line.strip().startswith(pattern):
                    skip = True
                    break
            if not skip and line.strip():
                content_lines.append(line)

        return "\n".join(content_lines).strip()

    def is_model_available(self, model_id: str) -> bool:
        """检查 GGUF 模型是否可用"""
        if Path(model_id).exists():
            return True

        # 检查模型键名
        model_path = self._get_model_path(model_id)
        return model_path is not None

    def list_models(self) -> List[Dict[str, Any]]:
        """列出本地缓存的 GGUF 模型"""
        models = []

        # 从配置中获取模型
        if self.config:
            for key, info in self.config.get("models", {}).items():
                path = self._get_model_path(key)
                if path:
                    models.append({
                        "key": key,
                        "alias": info.get("alias", key),
                        "path": path,
                        "backend": "llamacpp",
                        "memory_gb": info.get("memory_gb")
                    })

        # 扫描 HuggingFace 缓存中的 GGUF 文件
        if self._hf_cache.exists():
            for model_dir in self._hf_cache.iterdir():
                if model_dir.is_dir() and model_dir.name.startswith("models--"):
                    # 查找 GGUF 文件
                    snapshots_dir = model_dir / "snapshots"
                    if snapshots_dir.exists():
                        for snapshot in snapshots_dir.iterdir():
                            for gguf_file in snapshot.glob("*.gguf"):
                                if "mmproj" not in gguf_file.name.lower():
                                    models.append({
                                        "id": gguf_file.name,
                                        "path": str(gguf_file),
                                        "backend": "llamacpp"
                                    })

        return models

    def download_model(self, model_key: str) -> Tuple[bool, str]:
        """
        下载 GGUF 模型

        Args:
            model_key: 模型键名

        Returns:
            (成功标志, 消息)
        """
        model_info = self.GGUF_MODEL_MAP.get(model_key)
        if not model_info:
            return False, f"未知的模型: {model_key}"

        hf_repo = model_info["hf_repo"]
        gguf_file = model_info["gguf_file"]
        mmproj_file = model_info.get("mmproj_file")

        try:
            # 使用 huggingface-cli 下载
            files_to_download = [gguf_file]
            if mmproj_file:
                files_to_download.append(mmproj_file)

            for file in files_to_download:
                cmd = [
                    "huggingface-cli",
                    "download",
                    hf_repo,
                    file,
                    "--local-dir",
                    str(self._hf_cache / f"models--{hf_repo.replace('/', '--')}"),
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

                if result.returncode != 0:
                    return False, f"下载 {file} 失败: {result.stderr}"

            return True, f"模型 {model_key} 下载完成"

        except Exception as e:
            return False, f"下载失败: {str(e)}"