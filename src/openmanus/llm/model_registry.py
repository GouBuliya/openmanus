"""
@PURPOSE: 实现模型注册表，管理可用模型定义
@OUTLINE:
    - class ModelInfo: 模型信息
    - class ModelRegistry: 模型注册表
@DEPENDENCIES:
    - 外部: pydantic
"""

from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(str, Enum):
    """模型供应商"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GOOGLE = "google"
    LOCAL = "local"


@dataclass
class ModelInfo:
    """模型信息"""

    model_id: str
    provider: ModelProvider
    display_name: str
    max_tokens: int
    input_cost_per_1k: float  # USD
    output_cost_per_1k: float  # USD
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = True
    context_window: int = 8192
    tags: list[str] = field(default_factory=list)


class ModelRegistry:
    """
    模型注册表

    管理可用模型的定义和查询。

    Example:
        >>> registry = ModelRegistry()
        >>> model = registry.get("gpt-4")
        >>> print(model.max_tokens)
    """

    # 预定义模型
    BUILTIN_MODELS = [
        ModelInfo(
            model_id="gpt-4",
            provider=ModelProvider.OPENAI,
            display_name="GPT-4",
            max_tokens=8192,
            input_cost_per_1k=0.03,
            output_cost_per_1k=0.06,
            supports_vision=False,
            supports_function_calling=True,
            context_window=8192,
            tags=["reasoning", "coding"],
        ),
        ModelInfo(
            model_id="gpt-4-turbo",
            provider=ModelProvider.OPENAI,
            display_name="GPT-4 Turbo",
            max_tokens=4096,
            input_cost_per_1k=0.01,
            output_cost_per_1k=0.03,
            supports_vision=True,
            supports_function_calling=True,
            context_window=128000,
            tags=["reasoning", "coding", "vision"],
        ),
        ModelInfo(
            model_id="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI,
            display_name="GPT-3.5 Turbo",
            max_tokens=4096,
            input_cost_per_1k=0.0005,
            output_cost_per_1k=0.0015,
            supports_function_calling=True,
            context_window=16385,
            tags=["fast", "cheap"],
        ),
        ModelInfo(
            model_id="claude-3-opus",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude 3 Opus",
            max_tokens=4096,
            input_cost_per_1k=0.015,
            output_cost_per_1k=0.075,
            supports_vision=True,
            context_window=200000,
            tags=["reasoning", "long-context"],
        ),
        ModelInfo(
            model_id="claude-3-sonnet",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude 3 Sonnet",
            max_tokens=4096,
            input_cost_per_1k=0.003,
            output_cost_per_1k=0.015,
            supports_vision=True,
            context_window=200000,
            tags=["balanced"],
        ),
        ModelInfo(
            model_id="claude-3-haiku",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude 3 Haiku",
            max_tokens=4096,
            input_cost_per_1k=0.00025,
            output_cost_per_1k=0.00125,
            supports_vision=True,
            context_window=200000,
            tags=["fast", "cheap"],
        ),
        ModelInfo(
            model_id="deepseek-chat",
            provider=ModelProvider.DEEPSEEK,
            display_name="DeepSeek Chat",
            max_tokens=4096,
            input_cost_per_1k=0.0001,
            output_cost_per_1k=0.0002,
            context_window=32000,
            tags=["cheap", "coding"],
        ),
    ]

    def __init__(self) -> None:
        """初始化注册表"""
        self._models: dict[str, ModelInfo] = {}

        # 注册内置模型
        for model in self.BUILTIN_MODELS:
            self._models[model.model_id] = model

    def register(self, model: ModelInfo) -> None:
        """
        注册模型

        Args:
            model: 模型信息
        """
        self._models[model.model_id] = model

    def get(self, model_id: str) -> ModelInfo | None:
        """
        获取模型信息

        Args:
            model_id: 模型 ID

        Returns:
            模型信息
        """
        return self._models.get(model_id)

    def list_all(self) -> list[ModelInfo]:
        """列出所有模型"""
        return list(self._models.values())

    def list_by_provider(self, provider: ModelProvider) -> list[ModelInfo]:
        """按供应商列出模型"""
        return [m for m in self._models.values() if m.provider == provider]

    def list_by_tag(self, tag: str) -> list[ModelInfo]:
        """按标签列出模型"""
        return [m for m in self._models.values() if tag in m.tags]

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._models

    def __len__(self) -> int:
        return len(self._models)

    def __repr__(self) -> str:
        return f"<ModelRegistry models={len(self._models)}>"
