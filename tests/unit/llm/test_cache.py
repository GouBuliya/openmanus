"""
LLM 缓存单元测试
"""

import pytest

from openmanus.llm.adapters.base import CompletionRequest, CompletionResponse, Message, UsageInfo
from openmanus.llm.cache import MemoryLLMCache, create_cache


@pytest.fixture
def sample_request() -> CompletionRequest:
    """创建示例请求"""
    return CompletionRequest(
        model="gpt-4",
        messages=[
            Message(role="user", content="Hello!"),
        ],
        temperature=0.7,
        max_tokens=100,
    )


@pytest.fixture
def sample_response() -> CompletionResponse:
    """创建示例响应"""
    return CompletionResponse(
        content="Hello! How can I help you?",
        model="gpt-4",
        usage=UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        finish_reason="stop",
        latency_ms=100.0,
        cost_usd=0.001,
    )


class TestMemoryLLMCache:
    """测试内存缓存"""

    @pytest.mark.asyncio
    async def test_cache_miss(self, sample_request: CompletionRequest) -> None:
        """测试缓存未命中"""
        cache = MemoryLLMCache()
        result = await cache.get(sample_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit(
        self, sample_request: CompletionRequest, sample_response: CompletionResponse
    ) -> None:
        """测试缓存命中"""
        cache = MemoryLLMCache()
        await cache.set(sample_request, sample_response)
        result = await cache.get(sample_request)

        assert result is not None
        assert result.content == sample_response.content
        assert result.model == sample_response.model

    @pytest.mark.asyncio
    async def test_cache_delete(
        self, sample_request: CompletionRequest, sample_response: CompletionResponse
    ) -> None:
        """测试删除缓存"""
        cache = MemoryLLMCache()
        await cache.set(sample_request, sample_response)

        result = await cache.delete(sample_request)
        assert result is True

        cached = await cache.get(sample_request)
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_clear(
        self, sample_request: CompletionRequest, sample_response: CompletionResponse
    ) -> None:
        """测试清空缓存"""
        cache = MemoryLLMCache()
        await cache.set(sample_request, sample_response)
        await cache.clear()

        result = await cache.get(sample_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, sample_response: CompletionResponse) -> None:
        """测试 LRU 淘汰"""
        cache = MemoryLLMCache(max_size=2)

        # 添加 3 个条目
        for i in range(3):
            request = CompletionRequest(
                model="gpt-4",
                messages=[Message(role="user", content=f"Message {i}")],
            )
            await cache.set(request, sample_response)

        # 第一个条目应该被淘汰
        first_request = CompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Message 0")],
        )
        result = await cache.get(first_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_key_deterministic(
        self, sample_request: CompletionRequest, sample_response: CompletionResponse
    ) -> None:
        """测试缓存 Key 是确定性的"""
        cache = MemoryLLMCache()

        # 相同请求应该有相同的 key
        key1 = cache._build_cache_key(sample_request)
        key2 = cache._build_cache_key(sample_request)
        assert key1 == key2

        # 不同请求应该有不同的 key
        different_request = CompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Different message")],
        )
        key3 = cache._build_cache_key(different_request)
        assert key1 != key3


class TestCreateCache:
    """测试缓存工厂函数"""

    def test_create_memory_cache(self) -> None:
        """测试创建内存缓存"""
        cache = create_cache("memory", max_size=100)
        assert isinstance(cache, MemoryLLMCache)

    def test_create_unknown_cache(self) -> None:
        """测试创建未知类型缓存"""
        with pytest.raises(ValueError, match="Unknown cache type"):
            create_cache("unknown")
