"""
模型路由引擎 - 根据任务自动选择最合适的本地模型
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List


class ModelRouter:
    """模型路由器，根据任务内容选择合适的模型"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path.home() / ".claude" / "skills" / "local-commander" / "config" / "models.json"

        self.config = self._load_config(config_path)
        self.models = self.config.get("models", {})
        self.default_model = self.config.get("default_model", "coder")

    def _load_config(self, path: Path) -> Dict[str, Any]:
        """加载模型配置"""
        if not path.exists():
            raise FileNotFoundError(f"模型配置文件不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _is_model_for_backend(self, model_info: Dict[str, Any], backend: str) -> bool:
        """
        判断模型是否适用于指定后端

        Args:
            model_info: 模型配置信息
            backend: 后端类型 ("mlx" 或 "llamacpp")

        Returns:
            是否适用于该后端
        """
        model_id = model_info.get("id", "")
        hf_repo = model_info.get("hf_repo", "")
        gguf_file = model_info.get("gguf_file", "")

        if backend == "mlx":
            # MLX 后端: 需要有有效的模型 ID（本地路径或 HF 模型名）
            # 排除 GGUF 模型（hf_repo 包含 GGUF 或有 gguf_file）
            if gguf_file or "GGUF" in hf_repo.upper():
                return False
            return bool(model_id and ("/" in model_id or Path(model_id).exists()))
        else:
            # llama.cpp 后端: 需要有 GGUF 文件配置
            return bool(gguf_file or "GGUF" in hf_repo.upper())

    def get_models_for_backend(self, backend: str) -> Dict[str, Dict[str, Any]]:
        """
        获取适用于指定后端的模型列表

        Args:
            backend: 后端类型 ("mlx" 或 "llamacpp")

        Returns:
            适用于该后端的模型字典
        """
        return {
            key: info for key, info in self.models.items()
            if self._is_model_for_backend(info, backend)
        }

    def route(self, prompt: str, explicit_model: Optional[str] = None, backend: Optional[str] = None) -> Dict[str, Any]:
        """
        根据提示词选择模型

        Args:
            prompt: 用户输入的任务描述
            explicit_model: 用户显式指定的模型别名
            backend: 后端类型 ("mlx" 或 "llamacpp")，用于过滤模型

        Returns:
            包含模型信息的字典
        """
        # 如果用户显式指定了模型
        if explicit_model:
            return self._get_model_by_alias(explicit_model)

        # 获取适用于当前后端的模型
        available_models = self.models
        if backend:
            available_models = self.get_models_for_backend(backend)

        # 如果没有适用的模型，使用所有模型（向后兼容）
        if not available_models:
            available_models = self.models

        # 自动路由
        prompt_lower = prompt.lower()

        # 计算每个模型的匹配分数
        scores = {}
        for model_key, model_info in available_models.items():
            keywords = model_info.get("keywords", [])
            score = sum(1 for kw in keywords if kw in prompt_lower)
            scores[model_key] = score

        # 选择分数最高的模型
        best_model = max(scores, key=scores.get) if scores else self.default_model

        # 如果没有匹配到任何关键词，使用默认模型
        if scores[best_model] == 0:
            # 尝试使用后端适用的默认模型
            if backend and self.default_model in available_models:
                best_model = self.default_model
            elif available_models:
                # 使用第一个可用模型
                best_model = list(available_models.keys())[0]
            else:
                best_model = self.default_model

        return self._get_model_info(best_model)

    def _get_model_by_alias(self, alias: str) -> Dict[str, Any]:
        """根据别名获取模型"""
        for model_key, model_info in self.models.items():
            if model_info.get("alias") == alias or model_key == alias:
                return self._get_model_info(model_key)

        # 如果找不到，返回默认模型
        return self._get_model_info(self.default_model)

    def _get_model_info(self, model_key: str) -> Dict[str, Any]:
        """获取模型完整信息"""
        if model_key not in self.models:
            model_key = self.default_model

        info = self.models[model_key].copy()
        info["key"] = model_key

        # 确保 id 字段存在
        # 对于 GGUF 模型，id 可能是 hf_repo；对于 MLX 模型，id 是模型 ID
        if "id" not in info or not info["id"]:
            # 如果没有 id，使用 hf_repo 或 key 作为后备
            info["id"] = info.get("hf_repo", model_key)

        return info

    def list_models(self) -> list:
        """列出所有可用模型"""
        result = []
        for key, info in self.models.items():
            result.append({
                "key": key,
                "alias": info.get("alias", key),
                "id": info.get("id"),
                "memory_gb": info.get("memory_gb"),
                "use_cases": info.get("use_cases", [])
            })
        return result


# 单例实例
_router_instance = None

def get_router() -> ModelRouter:
    """获取路由器单例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance