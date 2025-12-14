"""
@PURPOSE: 实现 LLM 调用速率限制
@OUTLINE:
    - class RateLimiter: 速率限制器抽象基类
    - class RedisRateLimiter: Redis 速率限制器
    - class MemoryRateLimiter: 内存速率限制器 (用于测试)
    - class ModelRateLimits: 模型速率限制配置
@GOTCHAS:
    - 使用滑动窗口算法
    - RPM (请求/分钟) 和 TPM (Token/分钟) 双重限制
    - Redis 连接失败时默认允许请求 (fail-open)
@DEPENDENCIES:
    - 外部: redis
    - 内部: openmanus.config
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field

import redis.asyncio as redis
import structlog

from openmanus.config.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class ModelRateLimits:
    """
    模型速率限制配置

    Example:
        >>> limits = ModelRateLimits(rpm=60, tpm=100000)
    """

    rpm: int = 60  # 每分钟请求数
    tpm: int = 100000  # 每分钟 Token 数


@dataclass
class RateLimitResult:
    """
    速率限制检查结果

    Attributes:
        allowed: 是否允许请求
        wait_seconds: 需要等待的秒数 (仅当 allowed=False 时有效)
        reason: 限制原因 (rpm/tpm)
    """

    allowed: bool
    wait_seconds: float = 0.0
    reason: str | None = None


class RateLimiter(ABC):
    """
    速率限制器抽象基类

    所有速率限制器必须继承此类。
    """

    @abstractmethod
    async def check(
        self,
        model: str,
        estimated_tokens: int = 0,
    ) -> RateLimitResult:
        """
        检查是否允许请求

        Args:
            model: 模型名称
            estimated_tokens: 预估使用的 Token 数

        Returns:
            检查结果
        """
        ...

    @abstractmethod
    async def record(
        self,
        model: str,
        tokens: int,
    ) -> None:
        """
        记录一次请求

        Args:
            model: 模型名称
            tokens: 实际使用的 Token 数
        """
        ...

    @abstractmethod
    async def get_usage(self, model: str) -> dict[str, int]:
        """
        获取当前使用量

        Args:
            model: 模型名称

        Returns:
            当前 RPM 和 TPM 使用量
        """
        ...

    async def wait_if_needed(
        self,
        model: str,
        estimated_tokens: int = 0,
    ) -> None:
        """
        如果需要等待则等待

        Args:
            model: 模型名称
            estimated_tokens: 预估使用的 Token 数
        """
        result = await self.check(model, estimated_tokens)
        if not result.allowed:
            logger.info(
                "Rate limit wait",
                model=model,
                wait_seconds=result.wait_seconds,
                reason=result.reason,
            )
            await asyncio.sleep(result.wait_seconds)


class RedisRateLimiter(RateLimiter):
    """
    Redis 速率限制器

    使用 Redis 实现分布式速率限制。

    Features:
        - 滑动窗口算法
        - 支持 RPM 和 TPM 双重限制
        - 多实例共享限制状态

    Example:
        >>> limiter = RedisRateLimiter()
        >>> result = await limiter.check("gpt-4", estimated_tokens=1000)
        >>> if result.allowed:
        ...     # 执行请求
        ...     await limiter.record("gpt-4", actual_tokens)
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        default_limits: ModelRateLimits | None = None,
        model_limits: dict[str, ModelRateLimits] | None = None,
    ) -> None:
        """
        初始化 Redis 速率限制器

        Args:
            redis_client: Redis 客户端
            default_limits: 默认限制
            model_limits: 模型特定限制
        """
        settings = get_settings()

        if redis_client:
            self._redis = redis_client
        else:
            self._redis = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password or None,
                db=settings.redis.db,
            )

        self._default_limits = default_limits or ModelRateLimits(
            rpm=settings.llm.default_rpm,
            tpm=settings.llm.default_tpm,
        )
        self._model_limits = model_limits or {}

        logger.info(
            "RedisRateLimiter initialized",
            default_rpm=self._default_limits.rpm,
            default_tpm=self._default_limits.tpm,
        )

    def _get_limits(self, model: str) -> ModelRateLimits:
        """获取模型限制"""
        return self._model_limits.get(model, self._default_limits)

    async def check(
        self,
        model: str,
        estimated_tokens: int = 0,
    ) -> RateLimitResult:
        """检查是否允许请求"""
        limits = self._get_limits(model)
        now = time.time()
        window_start = now - 60  # 1 分钟滑动窗口

        try:
            # 检查 RPM
            rpm_key = f"ratelimit:rpm:{model}"
            rpm_count = await self._redis.zcount(rpm_key, window_start, now)

            if rpm_count >= limits.rpm:
                # 计算需要等待的时间
                oldest = await self._redis.zrange(rpm_key, 0, 0, withscores=True)
                if oldest:
                    wait_time = 60 - (now - float(oldest[0][1]))
                    return RateLimitResult(
                        allowed=False,
                        wait_seconds=max(0.0, wait_time),
                        reason="rpm",
                    )

            # 检查 TPM
            tpm_key = f"ratelimit:tpm:{model}"
            tpm_data = await self._redis.get(tpm_key)
            current_tpm = int(tpm_data) if tpm_data else 0

            if current_tpm + estimated_tokens > limits.tpm:
                return RateLimitResult(
                    allowed=False,
                    wait_seconds=60.0,  # 等待一个完整窗口
                    reason="tpm",
                )

            return RateLimitResult(allowed=True)

        except redis.RedisError as e:
            logger.warning("Rate limit check failed, allowing request", error=str(e))
            # Fail-open: Redis 不可用时允许请求
            return RateLimitResult(allowed=True)

    async def record(
        self,
        model: str,
        tokens: int,
    ) -> None:
        """记录一次请求"""
        now = time.time()

        try:
            # 记录 RPM
            rpm_key = f"ratelimit:rpm:{model}"
            await self._redis.zadd(rpm_key, {str(now): now})
            # 清理过期数据
            await self._redis.zremrangebyscore(rpm_key, 0, now - 60)
            await self._redis.expire(rpm_key, 120)  # 2 分钟过期

            # 记录 TPM (使用简单计数器)
            tpm_key = f"ratelimit:tpm:{model}"
            await self._redis.incrby(tpm_key, tokens)
            await self._redis.expire(tpm_key, 60)  # 1 分钟过期

            logger.debug("Rate limit recorded", model=model, tokens=tokens)

        except redis.RedisError as e:
            logger.warning("Rate limit record failed", model=model, error=str(e))

    async def get_usage(self, model: str) -> dict[str, int]:
        """获取当前使用量"""
        now = time.time()
        window_start = now - 60

        try:
            rpm_key = f"ratelimit:rpm:{model}"
            rpm_count = await self._redis.zcount(rpm_key, window_start, now)

            tpm_key = f"ratelimit:tpm:{model}"
            tpm_data = await self._redis.get(tpm_key)
            tpm_count = int(tpm_data) if tpm_data else 0

            limits = self._get_limits(model)

            return {
                "rpm_used": int(rpm_count),
                "rpm_limit": limits.rpm,
                "tpm_used": tpm_count,
                "tpm_limit": limits.tpm,
            }

        except redis.RedisError as e:
            logger.warning("Get usage failed", model=model, error=str(e))
            return {"rpm_used": 0, "rpm_limit": 0, "tpm_used": 0, "tpm_limit": 0}

    async def close(self) -> None:
        """关闭连接"""
        await self._redis.close()


class MemoryRateLimiter(RateLimiter):
    """
    内存速率限制器

    使用内存存储限制状态，主要用于测试和单实例部署。

    Example:
        >>> limiter = MemoryRateLimiter()
        >>> result = await limiter.check("gpt-4")
    """

    @dataclass
    class _WindowData:
        """滑动窗口数据"""

        requests: list[float] = field(default_factory=list)
        tokens: int = 0
        window_start: float = 0.0

    def __init__(
        self,
        default_limits: ModelRateLimits | None = None,
        model_limits: dict[str, ModelRateLimits] | None = None,
    ) -> None:
        """
        初始化内存速率限制器

        Args:
            default_limits: 默认限制
            model_limits: 模型特定限制
        """
        settings = get_settings()

        self._default_limits = default_limits or ModelRateLimits(
            rpm=settings.llm.default_rpm,
            tpm=settings.llm.default_tpm,
        )
        self._model_limits = model_limits or {}
        self._data: dict[str, MemoryRateLimiter._WindowData] = defaultdict(
            MemoryRateLimiter._WindowData
        )

        logger.info("MemoryRateLimiter initialized")

    def _get_limits(self, model: str) -> ModelRateLimits:
        """获取模型限制"""
        return self._model_limits.get(model, self._default_limits)

    def _clean_window(self, model: str, now: float) -> None:
        """清理过期数据"""
        data = self._data[model]
        window_start = now - 60

        # 清理过期请求
        data.requests = [t for t in data.requests if t > window_start]

        # 重置 Token 计数 (简化实现)
        if data.window_start < window_start:
            data.tokens = 0
            data.window_start = now

    async def check(
        self,
        model: str,
        estimated_tokens: int = 0,
    ) -> RateLimitResult:
        """检查是否允许请求"""
        limits = self._get_limits(model)
        now = time.time()

        self._clean_window(model, now)
        data = self._data[model]

        # 检查 RPM
        if len(data.requests) >= limits.rpm:
            oldest = min(data.requests) if data.requests else now
            wait_time = 60 - (now - oldest)
            return RateLimitResult(
                allowed=False,
                wait_seconds=max(0.0, wait_time),
                reason="rpm",
            )

        # 检查 TPM
        if data.tokens + estimated_tokens > limits.tpm:
            return RateLimitResult(
                allowed=False,
                wait_seconds=60.0,
                reason="tpm",
            )

        return RateLimitResult(allowed=True)

    async def record(
        self,
        model: str,
        tokens: int,
    ) -> None:
        """记录一次请求"""
        now = time.time()
        self._clean_window(model, now)

        data = self._data[model]
        data.requests.append(now)
        data.tokens += tokens

        logger.debug("Rate limit recorded", model=model, tokens=tokens)

    async def get_usage(self, model: str) -> dict[str, int]:
        """获取当前使用量"""
        now = time.time()
        self._clean_window(model, now)

        data = self._data[model]
        limits = self._get_limits(model)

        return {
            "rpm_used": len(data.requests),
            "rpm_limit": limits.rpm,
            "tpm_used": data.tokens,
            "tpm_limit": limits.tpm,
        }
