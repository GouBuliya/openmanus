"""
@PURPOSE: 实现 LLM 响应缓存
@OUTLINE:
    - class LLMCache: 缓存抽象基类
    - class RedisLLMCache: Redis 缓存实现
    - class MemoryLLMCache: 内存缓存实现 (用于测试)
    - def create_cache(): 缓存工厂函数
@GOTCHAS:
    - 缓存 Key 基于请求内容的 SHA256 哈希
    - Redis 连接失败时不会影响主流程
    - 内存缓存有大小限制，使用 LRU 淘汰
@DEPENDENCIES:
    - 外部: redis
    - 内部: openmanus.config, openmanus.llm.adapters.base
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections import OrderedDict

import redis.asyncio as redis
import structlog

from openmanus.config.settings import get_settings
from openmanus.llm.adapters.base import CompletionRequest, CompletionResponse

logger = structlog.get_logger(__name__)


class LLMCache(ABC):
    """
    LLM 缓存抽象基类

    所有缓存实现必须继承此类。

    Example:
        >>> cache = RedisLLMCache()
        >>> await cache.set(request, response)
        >>> cached = await cache.get(request)
    """

    @abstractmethod
    async def get(self, request: CompletionRequest) -> CompletionResponse | None:
        """
        获取缓存

        Args:
            request: 请求参数

        Returns:
            缓存的响应，未命中返回 None
        """
        ...

    @abstractmethod
    async def set(
        self,
        request: CompletionRequest,
        response: CompletionResponse,
        ttl: int | None = None,
    ) -> None:
        """
        设置缓存

        Args:
            request: 请求参数
            response: 响应结果
            ttl: 缓存 TTL(秒)，None 使用默认值
        """
        ...

    @abstractmethod
    async def delete(self, request: CompletionRequest) -> bool:
        """
        删除缓存

        Args:
            request: 请求参数

        Returns:
            是否删除成功
        """
        ...

    @abstractmethod
    async def clear(self) -> None:
        """清空所有缓存"""
        ...

    def _build_cache_key(self, request: CompletionRequest) -> str:
        """
        构建缓存 Key

        基于请求的关键参数生成唯一 Key。

        Args:
            request: 请求参数

        Returns:
            缓存 Key
        """
        key_data = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()
        return f"llm:cache:{key_hash}"


class RedisLLMCache(LLMCache):
    """
    Redis LLM 缓存

    使用 Redis 存储 LLM 响应缓存。

    Features:
        - 支持 TTL
        - 自动序列化/反序列化
        - 连接失败优雅降级

    Example:
        >>> cache = RedisLLMCache()
        >>> await cache.set(request, response, ttl=3600)
        >>> cached = await cache.get(request)
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        default_ttl: int | None = None,
        key_prefix: str = "llm:cache:",
    ) -> None:
        """
        初始化 Redis 缓存

        Args:
            redis_client: Redis 客户端，None 使用全局配置创建
            default_ttl: 默认 TTL(秒)，None 使用配置值
            key_prefix: 缓存 Key 前缀
        """
        settings = get_settings()
        self._default_ttl = default_ttl or settings.llm.cache_ttl_seconds
        self._key_prefix = key_prefix

        if redis_client:
            self._redis = redis_client
        else:
            self._redis = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password or None,
                db=settings.redis.db,
                decode_responses=True,
            )

        logger.info(
            "RedisLLMCache initialized",
            host=settings.redis.host,
            port=settings.redis.port,
            default_ttl=self._default_ttl,
        )

    async def get(self, request: CompletionRequest) -> CompletionResponse | None:
        """获取缓存"""
        key = self._build_cache_key(request)

        try:
            data = await self._redis.get(key)
            if data:
                logger.debug("Cache hit", key=key[:50])
                return CompletionResponse.model_validate_json(data)
            logger.debug("Cache miss", key=key[:50])
            return None

        except redis.RedisError as e:
            logger.warning("Redis get failed", key=key[:50], error=str(e))
            return None

    async def set(
        self,
        request: CompletionRequest,
        response: CompletionResponse,
        ttl: int | None = None,
    ) -> None:
        """设置缓存"""
        key = self._build_cache_key(request)
        ttl = ttl or self._default_ttl

        try:
            await self._redis.setex(key, ttl, response.model_dump_json())
            logger.debug("Cache set", key=key[:50], ttl=ttl)

        except redis.RedisError as e:
            logger.warning("Redis set failed", key=key[:50], error=str(e))

    async def delete(self, request: CompletionRequest) -> bool:
        """删除缓存"""
        key = self._build_cache_key(request)

        try:
            result = await self._redis.delete(key)
            return bool(result)

        except redis.RedisError as e:
            logger.warning("Redis delete failed", key=key[:50], error=str(e))
            return False

    async def clear(self) -> None:
        """清空所有缓存"""
        try:
            # 使用 SCAN 避免阻塞
            cursor = 0
            pattern = f"{self._key_prefix}*"

            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break

            logger.info("Cache cleared", pattern=pattern)

        except redis.RedisError as e:
            logger.warning("Redis clear failed", error=str(e))

    async def close(self) -> None:
        """关闭连接"""
        await self._redis.close()


class MemoryLLMCache(LLMCache):
    """
    内存 LLM 缓存

    使用内存存储 LLM 响应缓存，主要用于测试。

    Features:
        - LRU 淘汰策略
        - 可配置最大条目数

    Example:
        >>> cache = MemoryLLMCache(max_size=100)
        >>> await cache.set(request, response)
    """

    def __init__(self, max_size: int = 1000) -> None:
        """
        初始化内存缓存

        Args:
            max_size: 最大缓存条目数
        """
        self._max_size = max_size
        self._cache: OrderedDict[str, CompletionResponse] = OrderedDict()
        logger.info("MemoryLLMCache initialized", max_size=max_size)

    async def get(self, request: CompletionRequest) -> CompletionResponse | None:
        """获取缓存"""
        key = self._build_cache_key(request)

        if key in self._cache:
            # 移动到末尾 (最近使用)
            self._cache.move_to_end(key)
            logger.debug("Cache hit", key=key[:50])
            return self._cache[key]

        logger.debug("Cache miss", key=key[:50])
        return None

    async def set(
        self,
        request: CompletionRequest,
        response: CompletionResponse,
        ttl: int | None = None,  # noqa: ARG002 - 内存缓存忽略 TTL
    ) -> None:
        """设置缓存"""
        key = self._build_cache_key(request)

        # LRU 淘汰
        if len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = response
        logger.debug("Cache set", key=key[:50])

    async def delete(self, request: CompletionRequest) -> bool:
        """删除缓存"""
        key = self._build_cache_key(request)

        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        logger.info("Cache cleared")


def create_cache(
    cache_type: str = "redis",
    **kwargs: object,
) -> LLMCache:
    """
    创建缓存实例

    Args:
        cache_type: 缓存类型 (redis/memory)
        **kwargs: 传递给缓存构造函数的参数

    Returns:
        缓存实例

    Example:
        >>> cache = create_cache("redis")
        >>> cache = create_cache("memory", max_size=100)
    """
    if cache_type == "redis":
        return RedisLLMCache(**kwargs)  # type: ignore[arg-type]
    if cache_type == "memory":
        return MemoryLLMCache(**kwargs)  # type: ignore[arg-type]

    raise ValueError(f"Unknown cache type: {cache_type}")
