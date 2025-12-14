"""
@PURPOSE: 实现 LLM 服务健康检查
@OUTLINE:
    - class LLMHealthChecker: LLM 健康检查器
        - check_model(): 检查单个模型
        - check_all(): 检查所有模型
        - get_healthy_models(): 获取健康模型列表
    - class HealthStatus: 健康状态
    - class ModelHealth: 模型健康信息
@GOTCHAS:
    - 健康检查使用最小 Token 请求
    - 支持并发检查多个模型
    - 缓存检查结果，避免频繁检查
@DEPENDENCIES:
    - 外部: litellm
    - 内部: openmanus.config, openmanus.llm.model_registry
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum

import structlog
from litellm import acompletion

from openmanus.config.settings import get_settings
from openmanus.llm.model_registry import ModelRegistry

logger = structlog.get_logger(__name__)


class HealthStatus(str, Enum):
    """健康状态"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"  # 部分功能可用
    UNKNOWN = "unknown"


@dataclass
class ModelHealth:
    """
    模型健康信息

    Attributes:
        model: 模型名称
        status: 健康状态
        latency_ms: 检查延迟(毫秒)
        error: 错误信息 (如果有)
        last_check: 最后检查时间戳
        consecutive_failures: 连续失败次数
    """

    model: str
    status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float = 0.0
    error: str | None = None
    last_check: float = 0.0
    consecutive_failures: int = 0


@dataclass
class HealthCheckResult:
    """
    健康检查结果

    Attributes:
        overall_status: 整体状态
        models: 各模型健康信息
        healthy_count: 健康模型数量
        total_count: 总模型数量
        check_duration_ms: 检查耗时(毫秒)
    """

    overall_status: HealthStatus
    models: dict[str, ModelHealth] = field(default_factory=dict)
    healthy_count: int = 0
    total_count: int = 0
    check_duration_ms: float = 0.0


class LLMHealthChecker:
    """
    LLM 健康检查器

    定期检查 LLM 模型可用性。

    Features:
        - 并发检查多个模型
        - 缓存检查结果
        - 支持降级状态检测

    Example:
        >>> checker = LLMHealthChecker()
        >>> result = await checker.check_all()
        >>> healthy_models = await checker.get_healthy_models()
    """

    def __init__(
        self,
        model_registry: ModelRegistry | None = None,
        cache_ttl_seconds: int = 60,
        timeout_seconds: int = 5,
        max_retries: int = 1,
    ) -> None:
        """
        初始化健康检查器

        Args:
            model_registry: 模型注册表
            cache_ttl_seconds: 缓存 TTL(秒)
            timeout_seconds: 检查超时时间(秒)
            max_retries: 最大重试次数
        """
        self._settings = get_settings().llm
        self._registry = model_registry or ModelRegistry()
        self._cache_ttl = cache_ttl_seconds
        self._timeout = timeout_seconds
        self._max_retries = max_retries

        # 缓存
        self._health_cache: dict[str, ModelHealth] = {}

        logger.info(
            "LLMHealthChecker initialized",
            cache_ttl=cache_ttl_seconds,
            timeout=timeout_seconds,
        )

    async def check_model(
        self,
        model: str,
        force: bool = False,
    ) -> ModelHealth:
        """
        检查单个模型健康状态

        Args:
            model: 模型名称
            force: 是否强制检查 (忽略缓存)

        Returns:
            模型健康信息
        """
        # 检查缓存
        if not force and model in self._health_cache:
            cached = self._health_cache[model]
            if time.time() - cached.last_check < self._cache_ttl:
                logger.debug("Health check cache hit", model=model)
                return cached

        # 执行检查
        start_time = time.time()
        health = ModelHealth(model=model, last_check=time.time())

        for attempt in range(self._max_retries + 1):
            try:
                response = await acompletion(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    timeout=self._timeout,
                )

                if response:
                    health.status = HealthStatus.HEALTHY
                    health.latency_ms = (time.time() - start_time) * 1000
                    health.error = None
                    health.consecutive_failures = 0

                    logger.debug(
                        "Health check passed",
                        model=model,
                        latency_ms=health.latency_ms,
                    )
                    break

            except Exception as e:
                health.error = str(e)
                health.consecutive_failures += 1

                if attempt < self._max_retries:
                    logger.debug(
                        "Health check retry",
                        model=model,
                        attempt=attempt + 1,
                        error=str(e),
                    )
                    await asyncio.sleep(0.5)
                else:
                    health.status = HealthStatus.UNHEALTHY
                    health.latency_ms = (time.time() - start_time) * 1000

                    logger.warning(
                        "Health check failed",
                        model=model,
                        error=str(e),
                    )

        # 更新缓存
        self._health_cache[model] = health

        return health

    async def check_all(
        self,
        models: list[str] | None = None,
        force: bool = False,
        concurrent_limit: int = 5,
    ) -> HealthCheckResult:
        """
        检查所有模型健康状态

        Args:
            models: 要检查的模型列表，None 表示所有已配置模型
            force: 是否强制检查
            concurrent_limit: 并发检查数量限制

        Returns:
            健康检查结果
        """
        start_time = time.time()

        # 获取要检查的模型
        if models is None:
            models = self._get_configured_models()

        if not models:
            return HealthCheckResult(
                overall_status=HealthStatus.UNKNOWN,
                check_duration_ms=0.0,
            )

        # 并发检查
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def check_with_semaphore(model: str) -> ModelHealth:
            async with semaphore:
                return await self.check_model(model, force=force)

        tasks = [check_with_semaphore(model) for model in models]
        results = await asyncio.gather(*tasks)

        # 汇总结果
        model_health = {h.model: h for h in results}
        healthy_count = sum(1 for h in results if h.status == HealthStatus.HEALTHY)
        total_count = len(results)

        # 计算整体状态
        if healthy_count == total_count:
            overall_status = HealthStatus.HEALTHY
        elif healthy_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNHEALTHY

        check_duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "Health check completed",
            overall_status=overall_status.value,
            healthy_count=healthy_count,
            total_count=total_count,
            duration_ms=check_duration_ms,
        )

        return HealthCheckResult(
            overall_status=overall_status,
            models=model_health,
            healthy_count=healthy_count,
            total_count=total_count,
            check_duration_ms=check_duration_ms,
        )

    async def get_healthy_models(
        self,
        force: bool = False,
    ) -> list[str]:
        """
        获取健康模型列表

        Args:
            force: 是否强制检查

        Returns:
            健康模型名称列表
        """
        result = await self.check_all(force=force)
        return [
            model
            for model, health in result.models.items()
            if health.status == HealthStatus.HEALTHY
        ]

    async def is_model_healthy(
        self,
        model: str,
        force: bool = False,
    ) -> bool:
        """
        检查模型是否健康

        Args:
            model: 模型名称
            force: 是否强制检查

        Returns:
            是否健康
        """
        health = await self.check_model(model, force=force)
        return health.status == HealthStatus.HEALTHY

    def get_cached_health(self, model: str) -> ModelHealth | None:
        """
        获取缓存的健康状态

        Args:
            model: 模型名称

        Returns:
            缓存的健康信息，没有返回 None
        """
        return self._health_cache.get(model)

    def clear_cache(self) -> None:
        """清空健康检查缓存"""
        self._health_cache.clear()
        logger.debug("Health check cache cleared")

    def _get_configured_models(self) -> list[str]:
        """获取已配置的模型列表"""
        models: list[str] = []

        # 基于配置的 API Key 判断哪些模型可用
        if self._settings.openai_api_key:
            models.extend([
                "gpt-4",
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-3.5-turbo",
            ])

        if self._settings.anthropic_api_key:
            models.extend([
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ])

        if self._settings.deepseek_api_key:
            models.extend([
                "deepseek/deepseek-chat",
            ])

        return models
