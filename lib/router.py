"""
模型路由引擎 - 根据任务自动选择最合适的本地模型
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any


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

    def route(self, prompt: str, explicit_model: Optional[str] = None) -> Dict[str, Any]:
        """
        根据提示词选择模型

        Args:
            prompt: 用户输入的任务描述
            explicit_model: 用户显式指定的模型别名

        Returns:
            包含模型信息的字典
        """
        # 如果用户显式指定了模型
        if explicit_model:
            return self._get_model_by_alias(explicit_model)

        # 自动路由
        prompt_lower = prompt.lower()

        # 计算每个模型的匹配分数
        scores = {}
        for model_key, model_info in self.models.items():
            keywords = model_info.get("keywords", [])
            score = sum(1 for kw in keywords if kw in prompt_lower)
            scores[model_key] = score

        # 选择分数最高的模型
        best_model = max(scores, key=scores.get)

        # 如果没有匹配到任何关键词，使用默认模型
        if scores[best_model] == 0:
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