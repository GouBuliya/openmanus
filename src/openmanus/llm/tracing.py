"""
@PURPOSE: 实现 LLM 调用的 OpenTelemetry 追踪
@OUTLINE:
    - class LLMTracer: LLM 追踪器
        - trace_completion(): 追踪完成请求
        - trace_stream_completion(): 追踪流式请求
    - def create_llm_span(): 创建 LLM Span
    - def add_llm_attributes(): 添加 LLM 属性
@GOTCHAS:
    - Span 属性遵循 OpenTelemetry LLM 语义约定
    - 可选记录请求/响应内容 (默认关闭以保护隐私)
    - 异常会自动记录到 Span
@DEPENDENCIES:
    - 外部: opentelemetry-api, opentelemetry-sdk
    - 内部: openmanus.config
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from openmanus.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from openmanus.llm.adapters.base import CompletionRequest, CompletionResponse

import structlog

logger = structlog.get_logger(__name__)

# OpenTelemetry LLM 语义约定属性名
LLM_SYSTEM = "gen_ai.system"
LLM_REQUEST_MODEL = "gen_ai.request.model"
LLM_RESPONSE_MODEL = "gen_ai.response.model"
LLM_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
LLM_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
LLM_RESPONSE_FINISH_REASON = "gen_ai.response.finish_reasons"
LLM_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
LLM_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
LLM_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"

# 自定义属性
LLM_LATENCY_MS = "llm.latency_ms"
LLM_COST_USD = "llm.cost_usd"
LLM_CACHE_HIT = "llm.cache_hit"
LLM_REQUEST_CONTENT = "llm.request.content"
LLM_RESPONSE_CONTENT = "llm.response.content"


class LLMTracer:
    """
    LLM 追踪器

    使用 OpenTelemetry 追踪 LLM 调用。

    Features:
        - 自动记录请求/响应元数据
        - 支持流式响应追踪
        - 可选记录内容 (默认关闭)
        - 异常自动记录

    Example:
        >>> tracer = LLMTracer()
        >>> async with tracer.trace_completion(request) as span:
        ...     response = await adapter.complete(request)
        ...     tracer.record_response(span, response)
    """

    def __init__(
        self,
        tracer_name: str = "openmanus.llm",
        log_requests: bool | None = None,
        log_responses: bool | None = None,
    ) -> None:
        """
        初始化追踪器

        Args:
            tracer_name: Tracer 名称
            log_requests: 是否记录请求内容
            log_responses: 是否记录响应内容
        """
        settings = get_settings().llm
        self._tracer = trace.get_tracer(tracer_name)
        self._log_requests = (
            log_requests if log_requests is not None else settings.log_requests
        )
        self._log_responses = (
            log_responses if log_responses is not None else settings.log_responses
        )

        logger.debug(
            "LLMTracer initialized",
            tracer_name=tracer_name,
            log_requests=self._log_requests,
            log_responses=self._log_responses,
        )

    @asynccontextmanager
    async def trace_completion(
        self,
        request: CompletionRequest,
        operation_name: str = "llm.completion",
    ) -> AsyncIterator[trace.Span]:
        """
        追踪完成请求

        Args:
            request: 请求参数
            operation_name: 操作名称

        Yields:
            OpenTelemetry Span

        Example:
            >>> async with tracer.trace_completion(request) as span:
            ...     response = await adapter.complete(request)
            ...     tracer.record_response(span, response)
        """
        with self._tracer.start_as_current_span(
            name=operation_name,
            kind=SpanKind.CLIENT,
        ) as span:
            # 记录请求属性
            self._add_request_attributes(span, request)

            try:
                yield span
            except Exception as e:
                # 记录异常
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    @asynccontextmanager
    async def trace_stream_completion(
        self,
        request: CompletionRequest,
        operation_name: str = "llm.stream_completion",
    ) -> AsyncIterator[trace.Span]:
        """
        追踪流式完成请求

        Args:
            request: 请求参数
            operation_name: 操作名称

        Yields:
            OpenTelemetry Span
        """
        with self._tracer.start_as_current_span(
            name=operation_name,
            kind=SpanKind.CLIENT,
        ) as span:
            self._add_request_attributes(span, request)
            span.set_attribute("llm.stream", True)

            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def record_response(
        self,
        span: trace.Span,
        response: CompletionResponse,
        cache_hit: bool = False,
    ) -> None:
        """
        记录响应到 Span

        Args:
            span: OpenTelemetry Span
            response: 响应结果
            cache_hit: 是否缓存命中
        """
        # 响应模型
        span.set_attribute(LLM_RESPONSE_MODEL, response.model)
        span.set_attribute(LLM_RESPONSE_FINISH_REASON, [response.finish_reason])

        # 使用量
        span.set_attribute(LLM_USAGE_INPUT_TOKENS, response.usage.prompt_tokens)
        span.set_attribute(LLM_USAGE_OUTPUT_TOKENS, response.usage.completion_tokens)
        span.set_attribute(LLM_USAGE_TOTAL_TOKENS, response.usage.total_tokens)

        # 自定义属性
        span.set_attribute(LLM_LATENCY_MS, response.latency_ms)
        span.set_attribute(LLM_COST_USD, response.cost_usd)
        span.set_attribute(LLM_CACHE_HIT, cache_hit)

        # 可选记录响应内容
        if self._log_responses:
            span.set_attribute(LLM_RESPONSE_CONTENT, response.content[:1000])

        # 设置成功状态
        span.set_status(Status(StatusCode.OK))

    def record_stream_complete(
        self,
        span: trace.Span,
        total_content: str,
        model: str,
        latency_ms: float,
    ) -> None:
        """
        记录流式响应完成

        Args:
            span: OpenTelemetry Span
            total_content: 完整响应内容
            model: 模型名称
            latency_ms: 延迟(毫秒)
        """
        span.set_attribute(LLM_RESPONSE_MODEL, model)
        span.set_attribute(LLM_LATENCY_MS, latency_ms)

        if self._log_responses:
            span.set_attribute(LLM_RESPONSE_CONTENT, total_content[:1000])

        span.set_status(Status(StatusCode.OK))

    def _add_request_attributes(
        self,
        span: trace.Span,
        request: CompletionRequest,
    ) -> None:
        """添加请求属性到 Span"""
        # 系统信息
        span.set_attribute(LLM_SYSTEM, "litellm")

        # 模型和参数
        span.set_attribute(LLM_REQUEST_MODEL, request.model)
        span.set_attribute(LLM_REQUEST_TEMPERATURE, request.temperature)
        span.set_attribute(LLM_REQUEST_MAX_TOKENS, request.max_tokens)

        # 消息数量
        span.set_attribute("llm.request.message_count", len(request.messages))

        # 可选记录请求内容
        if self._log_requests and request.messages:
            last_message = request.messages[-1].content
            span.set_attribute(LLM_REQUEST_CONTENT, last_message[:1000])

    def _detect_system(self, model: str) -> str:
        """检测 LLM 系统"""
        model_lower = model.lower()
        if "gpt" in model_lower or "openai" in model_lower:
            return "openai"
        if "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        if "deepseek" in model_lower:
            return "deepseek"
        if "gemini" in model_lower:
            return "google"
        return "unknown"


def create_llm_span(
    tracer: trace.Tracer,
    name: str,
    model: str,
    attributes: dict[str, Any] | None = None,
) -> trace.Span:
    """
    创建 LLM Span

    便捷函数，用于手动创建 Span。

    Args:
        tracer: OpenTelemetry Tracer
        name: Span 名称
        model: 模型名称
        attributes: 额外属性

    Returns:
        OpenTelemetry Span

    Example:
        >>> tracer = trace.get_tracer("my.tracer")
        >>> span = create_llm_span(tracer, "my.operation", "gpt-4")
    """
    span = tracer.start_span(
        name=name,
        kind=SpanKind.CLIENT,
    )

    span.set_attribute(LLM_SYSTEM, "litellm")
    span.set_attribute(LLM_REQUEST_MODEL, model)

    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)

    return span


def add_llm_attributes(
    span: trace.Span,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    latency_ms: float | None = None,
    cost_usd: float | None = None,
    finish_reason: str | None = None,
) -> None:
    """
    添加 LLM 属性到 Span

    便捷函数，用于手动添加属性。

    Args:
        span: OpenTelemetry Span
        prompt_tokens: 输入 Token 数
        completion_tokens: 输出 Token 数
        total_tokens: 总 Token 数
        latency_ms: 延迟(毫秒)
        cost_usd: 成本(USD)
        finish_reason: 结束原因
    """
    if prompt_tokens is not None:
        span.set_attribute(LLM_USAGE_INPUT_TOKENS, prompt_tokens)
    if completion_tokens is not None:
        span.set_attribute(LLM_USAGE_OUTPUT_TOKENS, completion_tokens)
    if total_tokens is not None:
        span.set_attribute(LLM_USAGE_TOTAL_TOKENS, total_tokens)
    if latency_ms is not None:
        span.set_attribute(LLM_LATENCY_MS, latency_ms)
    if cost_usd is not None:
        span.set_attribute(LLM_COST_USD, cost_usd)
    if finish_reason is not None:
        span.set_attribute(LLM_RESPONSE_FINISH_REASON, [finish_reason])
