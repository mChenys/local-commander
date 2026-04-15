"""
后端基类 - 定义统一的模型调用接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List


@dataclass
class BackendInfo:
    """后端信息"""
    name: str
    version: str
    platform: str
    supported_features: List[str]
    is_available: bool
    error_message: Optional[str] = None


class Backend(ABC):
    """模型后端抽象基类"""

    def __init__(self, config: Optional[dict] = None):
        """
        初始化后端

        Args:
            config: 模型配置字典
        """
        self.config = config or {}
        self._info: Optional[BackendInfo] = None

    @abstractmethod
    def get_info(self) -> BackendInfo:
        """
        获取后端信息

        Returns:
            BackendInfo 实例
        """
        pass

    @abstractmethod
    def execute(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        执行文本模型推理

        Args:
            model_id: 模型 ID 或路径
            prompt: 输入提示词
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            (成功标志, 输出文本, 元数据)
        """
        pass

    @abstractmethod
    def execute_vision(
        self,
        model_id: str,
        prompt: str,
        image_path: str,
        max_tokens: int = 4096,
        **kwargs
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        执行视觉模型推理

        Args:
            model_id: 模型 ID 或路径
            prompt: 输入提示词
            image_path: 图片路径
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数

        Returns:
            (成功标志, 输出文本, 元数据)
        """
        pass

    @abstractmethod
    def is_model_available(self, model_id: str) -> bool:
        """
        检查模型是否可用

        Args:
            model_id: 模型 ID 或路径

        Returns:
            模型是否存在
        """
        pass

    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """
        列出可用的模型

        Returns:
            模型信息列表
        """
        pass

    def format_prompt(self, prompt: str, model_id: str = None) -> str:
        """
        根据模型类型格式化提示词

        Args:
            prompt: 原始提示词
            model_id: 模型 ID (用于判断模型类型)

        Returns:
            格式化后的提示词
        """
        model_lower = (model_id or "").lower()

        # Gemma 格式
        if "gemma" in model_lower:
            return f'<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n'

        # Qwen 格式 (默认)
        return f'<|im_start|>system\nYou are a helpful assistant. 回复要简洁专业。<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n'

    def parse_output(self, raw_output: str) -> str:
        """
        解析模型输出，提取实际内容

        Args:
            raw_output: 原始输出

        Returns:
            解析后的内容
        """
        lines = raw_output.strip().split("\n")
        in_content = False
        content_lines = []

        for line in lines:
            if "==========" in line:
                if in_content:
                    break
                in_content = True
                continue

            if in_content:
                content_lines.append(line)

        if content_lines:
            return "\n".join(content_lines).strip()

        return raw_output
