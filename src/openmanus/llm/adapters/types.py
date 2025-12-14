"""
@PURPOSE: 定义 LLM 适配器扩展数据类型
@OUTLINE:
    - class ContentType: 内容类型枚举
    - class ImageDetail: 图像细节级别枚举
    - class ImageUrl: 图像 URL
    - class ContentPart: 消息内容部分 (支持多模态)
    - class ToolFunction: 工具函数定义
    - class Tool: 工具定义
    - class ToolCallResponse: 工具调用响应
    - class ExtendedMessage: 扩展消息 (支持多模态和工具调用)
    - class ExtendedCompletionRequest: 扩展完成请求
    - class ExtendedCompletionResponse: 扩展完成响应
    - class StreamChunk: 流式响应块
@GOTCHAS:
    - ExtendedMessage.content 可以是字符串或 ContentPart 列表
    - Tool.type 目前仅支持 "function"
@DEPENDENCIES:
    - 外部: pydantic
    - 内部: openmanus.llm.adapters.base
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from openmanus.llm.adapters.base import UsageInfo


class ContentType(str, Enum):
    """内容类型"""

    TEXT = "text"
    IMAGE_URL = "image_url"


class ImageDetail(str, Enum):
    """图像细节级别"""

    LOW = "low"
    HIGH = "high"
    AUTO = "auto"


class ImageUrl(BaseModel):
    """
    图像 URL

    用于多模态消息中的图像内容。

    Example:
        >>> image = ImageUrl(url="https://example.com/image.png")
        >>> image.detail
        <ImageDetail.AUTO: 'auto'>
    """

    url: str = Field(..., description="图像 URL 或 base64 数据")
    detail: ImageDetail = Field(default=ImageDetail.AUTO, description="细节级别")


class ContentPart(BaseModel):
    """
    消息内容部分 (支持多模态)

    用于构建包含文本和图像的混合消息。

    Example:
        >>> text_part = ContentPart(type=ContentType.TEXT, text="描述这张图片")
        >>> image_part = ContentPart(
        ...     type=ContentType.IMAGE_URL,
        ...     image_url=ImageUrl(url="https://example.com/image.png"),
        ... )
    """

    type: ContentType = Field(..., description="内容类型")
    text: str | None = Field(default=None, description="文本内容")
    image_url: ImageUrl | None = Field(default=None, description="图像 URL")


class ToolFunction(BaseModel):
    """
    工具函数定义

    定义 LLM 可调用的工具函数。

    Example:
        >>> func = ToolFunction(
        ...     name="get_weather",
        ...     description="获取天气信息",
        ...     parameters={
        ...         "type": "object",
        ...         "properties": {
        ...             "location": {"type": "string", "description": "城市名称"},
        ...         },
        ...         "required": ["location"],
        ...     },
        ... )
    """

    name: str = Field(..., description="函数名称")
    description: str = Field(..., description="函数描述")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema 格式的参数定义",
    )


class Tool(BaseModel):
    """
    工具定义

    封装工具类型和函数定义。

    Example:
        >>> tool = Tool(function=ToolFunction(name="search", description="搜索"))
    """

    type: Literal["function"] = Field(default="function", description="工具类型")
    function: ToolFunction = Field(..., description="函数定义")


class ToolCallResponse(BaseModel):
    """
    工具调用响应

    LLM 返回的工具调用请求。

    Example:
        >>> call = ToolCallResponse(
        ...     id="call_123",
        ...     function_name="get_weather",
        ...     arguments='{"location": "北京"}',
        ... )
    """

    id: str = Field(..., description="调用 ID")
    function_name: str = Field(..., description="函数名称")
    arguments: str = Field(..., description="JSON 格式的参数")


class ExtendedMessage(BaseModel):
    """
    扩展消息 (支持多模态和工具调用)

    相比基础 Message，支持：
    - 多模态内容 (文本 + 图像)
    - 工具调用结果

    Example:
        >>> # 普通文本消息
        >>> msg = ExtendedMessage(role="user", content="你好")

        >>> # 多模态消息
        >>> msg = ExtendedMessage(
        ...     role="user",
        ...     content=[
        ...         ContentPart(type=ContentType.TEXT, text="描述这张图片"),
        ...         ContentPart(
        ...             type=ContentType.IMAGE_URL,
        ...             image_url=ImageUrl(url="https://example.com/img.png"),
        ...         ),
        ...     ],
        ... )

        >>> # 工具调用结果消息
        >>> msg = ExtendedMessage(
        ...     role="tool",
        ...     content='{"weather": "晴"}',
        ...     tool_call_id="call_123",
        ... )
    """

    role: str = Field(..., description="角色: system/user/assistant/tool")
    content: str | list[ContentPart] | None = Field(
        default=None,
        description="消息内容，可以是字符串或多模态内容列表",
    )
    name: str | None = Field(default=None, description="发送者名称")
    tool_calls: list[ToolCallResponse] | None = Field(
        default=None,
        description="工具调用列表 (仅 assistant 角色)",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="工具调用 ID (仅 tool 角色)",
    )


class ExtendedCompletionRequest(BaseModel):
    """
    扩展完成请求

    相比基础 CompletionRequest，支持：
    - 工具调用 (Function Calling)
    - 多模态输入 (Vision)
    - 更多参数控制

    Example:
        >>> request = ExtendedCompletionRequest(
        ...     model="gpt-4",
        ...     messages=[
        ...         ExtendedMessage(role="system", content="你是一个助手"),
        ...         ExtendedMessage(role="user", content="你好"),
        ...     ],
        ...     tools=[
        ...         Tool(function=ToolFunction(name="search", description="搜索")),
        ...     ],
        ... )
    """

    model: str = Field(..., description="模型名称")
    messages: list[ExtendedMessage] = Field(..., description="消息列表")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度")
    max_tokens: int = Field(default=4096, ge=1, description="最大 Token")
    stop: list[str] | None = Field(default=None, description="停止词")
    stream: bool = Field(default=False, description="是否流式")
    tools: list[Tool] | None = Field(default=None, description="工具列表")
    tool_choice: str | dict[str, Any] | None = Field(
        default=None,
        description="工具选择策略: auto/none/required 或指定工具",
    )
    top_p: float | None = Field(default=None, ge=0, le=1, description="Top-P 采样")
    frequency_penalty: float | None = Field(
        default=None,
        ge=-2,
        le=2,
        description="频率惩罚",
    )
    presence_penalty: float | None = Field(
        default=None,
        ge=-2,
        le=2,
        description="存在惩罚",
    )
    seed: int | None = Field(default=None, description="随机种子")
    cache: bool = Field(default=True, description="是否使用缓存")
    cache_ttl: int | None = Field(default=None, description="缓存 TTL(秒)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ExtendedCompletionResponse(BaseModel):
    """
    扩展完成响应

    相比基础 CompletionResponse，支持：
    - 工具调用结果

    Example:
        >>> response = ExtendedCompletionResponse(
        ...     content="好的，让我帮你搜索",
        ...     model="gpt-4",
        ...     tool_calls=[
        ...         ToolCallResponse(
        ...             id="call_123",
        ...             function_name="search",
        ...             arguments='{"query": "天气"}',
        ...         ),
        ...     ],
        ... )
    """

    content: str | None = Field(default=None, description="响应内容")
    model: str = Field(..., description="实际使用的模型")
    usage: UsageInfo = Field(default_factory=UsageInfo, description="使用量信息")
    finish_reason: str = Field(default="stop", description="结束原因")
    tool_calls: list[ToolCallResponse] | None = Field(
        default=None,
        description="工具调用列表",
    )
    latency_ms: float = Field(default=0.0, description="延迟(毫秒)")
    cost_usd: float = Field(default=0.0, description="成本(USD)")


class StreamChunk(BaseModel):
    """
    流式响应块

    流式响应中的单个数据块。

    Example:
        >>> chunk = StreamChunk(content="Hello", finish_reason=None)
        >>> final_chunk = StreamChunk(
        ...     content="",
        ...     finish_reason="stop",
        ...     usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ... )
    """

    content: str = Field(default="", description="内容片段")
    finish_reason: str | None = Field(default=None, description="结束原因")
    tool_calls: list[ToolCallResponse] | None = Field(
        default=None,
        description="工具调用列表 (增量)",
    )
    usage: UsageInfo | None = Field(
        default=None,
        description="使用量信息 (仅最后一个 chunk)",
    )
