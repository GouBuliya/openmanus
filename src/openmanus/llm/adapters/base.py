"""
@PURPOSE: 定义 LLM 适配器接口
@OUTLINE:
    - class Message: 聊天消息
    - class CompletionRequest: 请求模型
    - class UsageInfo: 使用量信息
    - class CompletionResponse: 响应模型
    - class ILLMAdapter: LLM 适配器协议
@GOTCHAS:
    - ILLMAdapter 使用 Protocol 定义，支持结构化子类型
    - stream_complete 返回类型使用 Any 避免协变问题
@DEPENDENCIES:
    - 外部: pydantic
"""

from typing import Any, Protocol

from pydantic import BaseModel, Field


class Message(BaseModel):
    """聊天消息"""

    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class CompletionRequest(BaseModel):
    """LLM 请求"""

    model: str = Field(..., description="模型名称")
    messages: list[Message] = Field(..., description="消息列表")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1)
    stop: list[str] | None = Field(default=None)
    stream: bool = Field(default=False)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageInfo(BaseModel):
    """使用量信息"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class CompletionResponse(BaseModel):
    """LLM 响应"""

    content: str = Field(..., description="响应内容")
    model: str = Field(..., description="实际使用的模型")
    usage: UsageInfo = Field(default_factory=UsageInfo)
    finish_reason: str = Field(default="stop")
    latency_ms: float = Field(default=0.0)
    cost_usd: float = Field(default=0.0)


class ILLMAdapter(Protocol):
    """
    LLM 适配器协议

    所有 LLM 适配器必须实现此接口。

    Example:
        >>> adapter = LiteLLMAdapter()
        >>> response = await adapter.complete(request)
        >>> print(response.content)
    """

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        执行完成请求

        Args:
            request: 请求参数

        Returns:
            响应结果
        """
        ...

    async def stream_complete(
        self,
        request: CompletionRequest,
    ) -> Any:  # AsyncIterator[str]
        """
        流式完成请求

        Args:
            request: 请求参数

        Yields:
            响应内容片段
        """
        ...

    def get_supported_models(self) -> list[str]:
        """获取支持的模型列表"""
        ...

    async def health_check(self, model: str | None = None) -> bool:
        """
        健康检查

        Args:
            model: 要检查的模型，None 表示使用默认模型

        Returns:
            模型是否可用
        """
        ...

    def estimate_tokens(self, messages: list[Message]) -> int:
        """
        估算 Token 数量

        Args:
            messages: 消息列表

        Returns:
            估算的 Token 数量
        """
        ...

    def estimate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """
        估算成本

        Args:
            model: 模型名称
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数

        Returns:
            估算成本 (USD)
        """
        ...
