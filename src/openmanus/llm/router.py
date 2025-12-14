"""
@PURPOSE: 封装 LiteLLM Router 实现负载均衡和降级
@OUTLINE:
    - class LLMRouter: Router 封装
        - complete(): 带降级的完成请求
        - stream_complete(): 带降级的流式请求
        - health_check(): 健康检查
    - class RouterConfig: Router 配置
@GOTCHAS:
    - 需要配置多个模型才能实现负载均衡
    - Fallback 会自动在主模型失败时触发
    - 支持多种路由策略
@DEPENDENCIES:
    - 外部: litellm
    - 内部: openmanus.config, openmanus.llm.model_registry
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import structlog
from litellm import Router

from openmanus.config.settings import get_settings
from openmanus.core.exceptions import LLMError
from openmanus.llm.adapters.base import (
    CompletionRequest,
    CompletionResponse,
    UsageInfo,
)
from openmanus.llm.model_registry import ModelProvider, ModelRegistry

logger = structlog.get_logger(__name__)


@dataclass
class RouterConfig:
    """
    Router 配置

    Attributes:
        routing_strategy: 路由策略
        num_retries: 重试次数
        timeout: 超时时间(秒)
        fallback_models: 降级模型列表
        allowed_fails: 触发降级前允许的失败次数
        cooldown_time: 模型冷却时间(秒)
    """

    routing_strategy: str = "simple-shuffle"
    num_retries: int = 3
    timeout: int = 60
    fallback_models: list[str] = field(default_factory=list)
    allowed_fails: int = 2
    cooldown_time: int = 60


class LLMRouter:
    """
    LLM 路由器

    封装 LiteLLM Router，提供：
    - 多模型负载均衡
    - 自动降级
    - 健康检查

    Example:
        >>> router = LLMRouter()
        >>> response = await router.complete(request)
    """

    def __init__(
        self,
        config: RouterConfig | None = None,
        model_registry: ModelRegistry | None = None,
    ) -> None:
        """
        初始化 Router

        Args:
            config: Router 配置
            model_registry: 模型注册表
        """
        self._settings = get_settings().llm
        self._config = config or RouterConfig(
            routing_strategy=self._settings.routing_strategy,
            num_retries=self._settings.max_retries,
            timeout=self._settings.timeout_seconds,
            fallback_models=self._settings.fallback_models,
        )
        self._registry = model_registry or ModelRegistry()
        self._router = self._create_router()

        logger.info(
            "LLMRouter initialized",
            routing_strategy=self._config.routing_strategy,
            num_retries=self._config.num_retries,
        )

    def _create_router(self) -> Router:
        """创建 LiteLLM Router"""
        model_list = self._build_model_list()

        # 构建降级配置
        fallbacks = None
        if self._config.fallback_models:
            fallbacks = []
            # 为每个主模型配置降级
            for model_config in model_list:
                model_name = model_config["model_name"]
                if model_name not in self._config.fallback_models:
                    fallbacks.append({model_name: self._config.fallback_models})

        return Router(
            model_list=model_list,
            fallbacks=fallbacks,
            routing_strategy=self._config.routing_strategy,
            num_retries=self._config.num_retries,
            timeout=self._config.timeout,
            allowed_fails=self._config.allowed_fails,
            cooldown_time=self._config.cooldown_time,
        )

    def _build_model_list(self) -> list[dict[str, Any]]:
        """构建模型列表"""
        model_list: list[dict[str, Any]] = []
        settings = self._settings

        # OpenAI 模型
        if settings.openai_api_key:
            for model in self._registry.list_by_provider(ModelProvider.OPENAI):
                model_list.append({
                    "model_name": model.model_id,
                    "litellm_params": {
                        "model": model.model_id,
                        "api_key": settings.openai_api_key,
                        "api_base": settings.openai_api_base or None,
                    },
                    "tpm": settings.default_tpm,
                    "rpm": settings.default_rpm,
                })

        # Anthropic 模型
        if settings.anthropic_api_key:
            for model in self._registry.list_by_provider(ModelProvider.ANTHROPIC):
                model_list.append({
                    "model_name": model.model_id,
                    "litellm_params": {
                        "model": model.model_id,
                        "api_key": settings.anthropic_api_key,
                    },
                    "tpm": settings.default_tpm,
                    "rpm": settings.default_rpm,
                })

        # DeepSeek 模型
        if settings.deepseek_api_key:
            for model in self._registry.list_by_provider(ModelProvider.DEEPSEEK):
                model_list.append({
                    "model_name": model.model_id,
                    "litellm_params": {
                        "model": f"deepseek/{model.model_id}",
                        "api_key": settings.deepseek_api_key,
                        "api_base": settings.deepseek_api_base,
                    },
                    "tpm": settings.default_tpm,
                    "rpm": settings.default_rpm,
                })

        logger.debug("Model list built", count=len(model_list))
        return model_list

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        带降级的完成请求

        Args:
            request: 请求参数

        Returns:
            响应结果

        Raises:
            LLMError: 所有模型都失败
        """
        start_time = time.time()
        model = request.model or self._settings.default_model

        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        try:
            response = await self._router.acompletion(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stop=request.stop,
            )

            latency_ms = (time.time() - start_time) * 1000

            # 计算成本
            try:
                from litellm import completion_cost

                cost = completion_cost(completion_response=response)
            except Exception:
                cost = 0.0

            logger.info(
                "Router completion success",
                requested_model=model,
                actual_model=response.model,
                latency_ms=latency_ms,
            )

            return CompletionResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage=UsageInfo(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                ),
                finish_reason=response.choices[0].finish_reason or "stop",
                latency_ms=latency_ms,
                cost_usd=cost,
            )

        except Exception as e:
            logger.error(
                "Router completion failed",
                model=model,
                error=str(e),
            )
            raise LLMError(f"All models failed: {e}") from e

    async def stream_complete(
        self,
        request: CompletionRequest,
    ) -> AsyncIterator[str]:
        """
        带降级的流式完成请求

        Args:
            request: 请求参数

        Yields:
            响应内容片段
        """
        model = request.model or self._settings.default_model
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        try:
            response = await self._router.acompletion(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stop=request.stop,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error("Router stream failed", model=model, error=str(e))
            raise LLMError(f"Stream failed: {e}") from e

    async def health_check(self) -> dict[str, bool]:
        """
        检查所有模型健康状态

        Returns:
            模型名称到健康状态的映射
        """
        health_status: dict[str, bool] = {}

        for model_config in self._router.model_list:
            model_name = model_config["model_name"]
            try:
                response = await self._router.acompletion(
                    model=model_name,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    timeout=5,
                )
                health_status[model_name] = response is not None
            except Exception as e:
                logger.warning(
                    "Model health check failed",
                    model=model_name,
                    error=str(e),
                )
                health_status[model_name] = False

        return health_status

    def get_available_models(self) -> list[str]:
        """获取可用模型列表"""
        return [m["model_name"] for m in self._router.model_list]

    def get_healthy_models(self) -> list[str]:
        """
        获取健康模型列表

        注意：这是同步方法，返回最近一次健康检查的结果
        """
        try:
            return [
                name
                for name, info in self._router.healthy_deployments.items()
                if info.get("healthy", True)
            ]
        except Exception:
            return self.get_available_models()
