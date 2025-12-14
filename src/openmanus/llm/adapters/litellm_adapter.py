"""
@PURPOSE: 实现基于 LiteLLM 的统一 LLM 适配器
@OUTLINE:
    - class LiteLLMAdapter: 统一 LLM 适配器
        - complete(): 同步完成请求
        - stream_complete(): 流式完成请求
        - complete_with_tools(): 带工具调用的请求
        - health_check(): 健康检查
        - estimate_tokens(): Token 估算
        - estimate_cost(): 成本估算
        - _execute_with_retry(): 带重试的执行
        - _setup_litellm(): 配置 LiteLLM
        - _build_params(): 构建请求参数
        - _parse_response(): 解析响应
        - _handle_error(): 错误处理
@GOTCHAS:
    - API Key 通过环境变量或配置注入
    - 流式响应使用异步迭代器
    - 重试使用 Tenacity 指数退避
    - 缓存需要外部注入
@DEPENDENCIES:
    - 外部: litellm, tenacity
    - 内部: openmanus.config, openmanus.core.exceptions
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import litellm
from litellm import acompletion, completion_cost, token_counter
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadRequestError,
    ContentPolicyViolationError,
    ContextWindowExceededError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from openmanus.config.settings import LLMSettings, get_settings
from openmanus.core.exceptions import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMContextLengthError,
    LLMError,
    LLMInvalidRequestError,
    LLMModelNotAvailableError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from openmanus.llm.adapters.base import (
    CompletionRequest,
    CompletionResponse,
    Message,
    UsageInfo,
)

if TYPE_CHECKING:
    from openmanus.llm.adapters.types import (
        ExtendedCompletionRequest,
        ExtendedCompletionResponse,
    )
    from openmanus.llm.cache import LLMCache

import structlog

logger = structlog.get_logger(__name__)


class LiteLLMAdapter:
    """
    基于 LiteLLM 的统一适配器

    支持多个 LLM 供应商的统一调用，包括 OpenAI、Anthropic、DeepSeek 等。

    Features:
        - 统一接口调用多个供应商
        - 自动重试和指数退避
        - 成本追踪和 Token 估算
        - 可选缓存支持
        - 健康检查

    Example:
        >>> adapter = LiteLLMAdapter()
        >>> request = CompletionRequest(
        ...     model="gpt-4",
        ...     messages=[Message(role="user", content="Hello")],
        ... )
        >>> response = await adapter.complete(request)
        >>> print(response.content)
    """

    # 支持的模型列表
    SUPPORTED_MODELS: list[str] = [
        # OpenAI
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
        # Anthropic
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20241022",
        # DeepSeek
        "deepseek/deepseek-chat",
        "deepseek/deepseek-coder",
    ]

    def __init__(
        self,
        settings: LLMSettings | None = None,
        cache: LLMCache | None = None,
    ) -> None:
        """
        初始化适配器

        Args:
            settings: LLM 配置，None 表示使用全局配置
            cache: 可选的缓存实例
        """
        self._settings = settings or get_settings().llm
        self._cache = cache
        self._setup_litellm()

        logger.info(
            "LiteLLMAdapter initialized",
            default_model=self._settings.default_model,
            cache_enabled=cache is not None,
        )

    def _setup_litellm(self) -> None:
        """配置 LiteLLM 全局设置"""
        # 设置 API Keys
        if self._settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self._settings.openai_api_key
        if self._settings.openai_api_base:
            os.environ["OPENAI_API_BASE"] = self._settings.openai_api_base
        if self._settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self._settings.anthropic_api_key
        if self._settings.deepseek_api_key:
            os.environ["DEEPSEEK_API_KEY"] = self._settings.deepseek_api_key

        # LiteLLM 全局配置
        litellm.drop_params = True  # 自动丢弃不支持的参数
        litellm.set_verbose = False  # 关闭详细日志

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        执行完成请求

        Args:
            request: 请求参数

        Returns:
            响应结果

        Raises:
            LLMError: LLM 调用失败
            LLMRateLimitError: 速率限制
            LLMTimeoutError: 请求超时
        """
        start_time = time.time()
        model = request.model or self._settings.default_model

        # 检查缓存
        if self._cache and not request.stream:
            cached = await self._cache.get(request)
            if cached:
                logger.debug("Cache hit", model=model)
                cached.latency_ms = (time.time() - start_time) * 1000
                return cached

        # 构建参数
        params = self._build_params(request)

        try:
            # 执行请求 (带重试)
            response = await self._execute_with_retry(params)

            # 解析响应
            result = self._parse_response(response, model, start_time)

            # 写入缓存
            if self._cache:
                await self._cache.set(request, result)

            logger.info(
                "LLM completion success",
                model=result.model,
                tokens=result.usage.total_tokens,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
            )

            return result

        except Exception as e:
            self._handle_error(e, model)
            raise  # _handle_error 会抛出异常，这行不会执行

    async def stream_complete(
        self,
        request: CompletionRequest,
    ) -> AsyncIterator[str]:
        """
        流式完成请求

        Args:
            request: 请求参数

        Yields:
            响应内容片段

        Raises:
            LLMError: LLM 调用失败
        """
        model = request.model or self._settings.default_model
        params = self._build_params(request)
        params["stream"] = True
        params["stream_options"] = {"include_usage": True}

        logger.debug("Starting stream completion", model=model)

        try:
            response = await acompletion(**params)

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error("Stream completion failed", model=model, error=str(e))
            self._handle_error(e, model)

    async def complete_with_tools(
        self,
        request: ExtendedCompletionRequest,
    ) -> ExtendedCompletionResponse:
        """
        带工具调用的完成请求

        Args:
            request: 扩展请求参数

        Returns:
            扩展响应结果
        """
        from openmanus.llm.adapters.types import (
            ExtendedCompletionResponse,
            ToolCallResponse,
        )

        start_time = time.time()
        model = request.model or self._settings.default_model

        # 构建消息
        messages = []
        for msg in request.messages:
            if isinstance(msg.content, str):
                messages.append({"role": msg.role, "content": msg.content})
            elif msg.content is not None:
                # 多模态消息
                content_parts = []
                for part in msg.content:
                    if part.type.value == "text":
                        content_parts.append({"type": "text", "text": part.text})
                    elif part.type.value == "image_url" and part.image_url:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": part.image_url.url,
                                "detail": part.image_url.detail.value,
                            },
                        })
                messages.append({"role": msg.role, "content": content_parts})
            elif msg.tool_calls:
                messages.append({
                    "role": msg.role,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function_name,
                                "arguments": tc.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })
            elif msg.tool_call_id:
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or "",
                })

        # 构建工具定义
        tools = None
        if request.tools:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.function.name,
                        "description": tool.function.description,
                        "parameters": tool.function.parameters,
                    },
                }
                for tool in request.tools
            ]

        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "timeout": self._settings.timeout_seconds,
        }

        if tools:
            params["tools"] = tools
        if request.tool_choice:
            params["tool_choice"] = request.tool_choice
        if request.stop:
            params["stop"] = request.stop

        try:
            response = await self._execute_with_retry(params)

            # 解析工具调用
            tool_calls = None
            if response.choices[0].message.tool_calls:
                tool_calls = [
                    ToolCallResponse(
                        id=tc.id,
                        function_name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                    for tc in response.choices[0].message.tool_calls
                ]

            # 计算成本
            cost = completion_cost(completion_response=response)

            return ExtendedCompletionResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage=UsageInfo(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                ),
                finish_reason=response.choices[0].finish_reason or "stop",
                tool_calls=tool_calls,
                latency_ms=(time.time() - start_time) * 1000,
                cost_usd=cost,
            )

        except Exception as e:
            self._handle_error(e, model)
            raise

    async def health_check(self, model: str | None = None) -> bool:
        """
        健康检查

        Args:
            model: 要检查的模型，None 表示使用默认模型

        Returns:
            模型是否可用
        """
        check_model = model or self._settings.default_model

        try:
            response = await acompletion(
                model=check_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                timeout=5,
            )
            return response is not None

        except Exception as e:
            logger.warning(
                "Health check failed",
                model=check_model,
                error=str(e),
            )
            return False

    def estimate_tokens(self, messages: list[Message]) -> int:
        """
        估算 Token 数量

        Args:
            messages: 消息列表

        Returns:
            估算的 Token 数量
        """
        text = " ".join(m.content for m in messages)
        return token_counter(model=self._settings.default_model, text=text)

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
        try:
            # 使用 litellm 的成本计算
            from litellm import cost_per_token

            prompt_cost, completion_cost_val = cost_per_token(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return prompt_cost + completion_cost_val
        except Exception:
            # 降级到简单估算
            return (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)

    def get_supported_models(self) -> list[str]:
        """获取支持的模型列表"""
        return self.SUPPORTED_MODELS.copy()

    def _build_params(self, request: CompletionRequest) -> dict[str, Any]:
        """
        构建 LiteLLM 调用参数

        Args:
            request: 请求参数

        Returns:
            LiteLLM 参数字典
        """
        messages = [
            {"role": m.role, "content": m.content} for m in request.messages
        ]

        params: dict[str, Any] = {
            "model": request.model or self._settings.default_model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "timeout": self._settings.timeout_seconds,
        }

        if request.stop:
            params["stop"] = request.stop

        return params

    @retry(
        retry=retry_if_exception_type((RateLimitError, ServiceUnavailableError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        reraise=True,
    )
    async def _execute_with_retry(self, params: dict[str, Any]) -> Any:
        """
        带重试的执行请求

        Args:
            params: LiteLLM 参数

        Returns:
            LiteLLM 响应
        """
        return await acompletion(**params)

    def _parse_response(
        self,
        response: Any,
        model: str,
        start_time: float,
    ) -> CompletionResponse:
        """
        解析 LiteLLM 响应

        Args:
            response: LiteLLM 响应
            model: 请求的模型名称
            start_time: 请求开始时间

        Returns:
            CompletionResponse
        """
        content = response.choices[0].message.content or ""

        usage = UsageInfo(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )

        # 使用 LiteLLM 内置成本计算
        try:
            cost = completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        return CompletionResponse(
            content=content,
            model=response.model,
            usage=usage,
            finish_reason=response.choices[0].finish_reason or "stop",
            latency_ms=(time.time() - start_time) * 1000,
            cost_usd=cost,
        )

    def _handle_error(self, error: Exception, model: str) -> None:
        """
        处理 LiteLLM 错误

        Args:
            error: 原始异常
            model: 模型名称

        Raises:
            对应的 OpenManus 异常
        """
        logger.error(
            "LLM call failed",
            model=model,
            error_type=type(error).__name__,
            error=str(error),
        )

        if isinstance(error, RateLimitError):
            raise LLMRateLimitError(str(error))

        if isinstance(error, Timeout):
            raise LLMTimeoutError(model, self._settings.timeout_seconds)

        if isinstance(error, AuthenticationError):
            raise LLMAuthenticationError("unknown", str(error))

        if isinstance(error, ContextWindowExceededError):
            raise LLMContextLengthError(model, 0, 0)

        if isinstance(error, ContentPolicyViolationError):
            raise LLMContentFilterError(model, str(error))

        if isinstance(error, NotFoundError):
            raise LLMModelNotAvailableError(model, str(error))

        if isinstance(error, BadRequestError):
            raise LLMInvalidRequestError(str(error))

        if isinstance(error, (APIError, APIConnectionError)):
            raise LLMProviderError(str(error))

        # 未知错误
        raise LLMError(str(error))

    def __repr__(self) -> str:
        return f"<LiteLLMAdapter default_model={self._settings.default_model}>"
