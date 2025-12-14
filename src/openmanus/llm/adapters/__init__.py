"""
@PURPOSE: LLM 适配器包
@OUTLINE:
    - ILLMAdapter: 适配器接口
    - LiteLLMAdapter: 统一适配器
    - types: 扩展类型定义
@DEPENDENCIES:
    - 外部: litellm
"""

from openmanus.llm.adapters.base import (
    CompletionRequest,
    CompletionResponse,
    ILLMAdapter,
    Message,
    UsageInfo,
)
from openmanus.llm.adapters.litellm_adapter import LiteLLMAdapter
from openmanus.llm.adapters.types import (
    ContentPart,
    ContentType,
    ExtendedCompletionRequest,
    ExtendedCompletionResponse,
    ExtendedMessage,
    ImageDetail,
    ImageUrl,
    StreamChunk,
    Tool,
    ToolCallResponse,
    ToolFunction,
)

__all__ = [
    # 基础类型
    "Message",
    "CompletionRequest",
    "CompletionResponse",
    "UsageInfo",
    # 扩展类型
    "ContentType",
    "ContentPart",
    "ImageDetail",
    "ImageUrl",
    "Tool",
    "ToolFunction",
    "ToolCallResponse",
    "ExtendedMessage",
    "ExtendedCompletionRequest",
    "ExtendedCompletionResponse",
    "StreamChunk",
    # 接口和实现
    "ILLMAdapter",
    "LiteLLMAdapter",
]
