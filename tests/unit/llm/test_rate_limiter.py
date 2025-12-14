"""
速率限制器单元测试
"""

import pytest

from openmanus.llm.rate_limiter import MemoryRateLimiter, ModelRateLimits


class TestMemoryRateLimiter:
    """测试内存速率限制器"""

    @pytest.fixture
    def limiter(self) -> MemoryRateLimiter:
        """创建速率限制器实例"""
        return MemoryRateLimiter(
            default_limits=ModelRateLimits(rpm=5, tpm=1000),
        )

    @pytest.mark.asyncio
    async def test_check_allows_first_request(self, limiter: MemoryRateLimiter) -> None:
        """测试第一个请求允许通过"""
        result = await limiter.check("gpt-4")
        assert result.allowed is True
        assert result.wait_seconds == 0.0

    @pytest.mark.asyncio
    async def test_check_rpm_limit(self, limiter: MemoryRateLimiter) -> None:
        """测试 RPM 限制"""
        # 记录 5 个请求 (达到限制)
        for _ in range(5):
            await limiter.record("gpt-4", tokens=10)

        # 第 6 个请求应该被拒绝
        result = await limiter.check("gpt-4")
        assert result.allowed is False
        assert result.reason == "rpm"

    @pytest.mark.asyncio
    async def test_check_tpm_limit(self, limiter: MemoryRateLimiter) -> None:
        """测试 TPM 限制"""
        # 记录大量 Token (超过限制)
        await limiter.record("gpt-4", tokens=1000)

        # 下一个请求应该被拒绝
        result = await limiter.check("gpt-4", estimated_tokens=100)
        assert result.allowed is False
        assert result.reason == "tpm"

    @pytest.mark.asyncio
    async def test_record_usage(self, limiter: MemoryRateLimiter) -> None:
        """测试记录使用量"""
        await limiter.record("gpt-4", tokens=100)
        await limiter.record("gpt-4", tokens=200)

        usage = await limiter.get_usage("gpt-4")
        assert usage["rpm_used"] == 2
        assert usage["tpm_used"] == 300

    @pytest.mark.asyncio
    async def test_model_specific_limits(self) -> None:
        """测试模型特定限制"""
        limiter = MemoryRateLimiter(
            default_limits=ModelRateLimits(rpm=10, tpm=1000),
            model_limits={
                "gpt-4": ModelRateLimits(rpm=5, tpm=500),
            },
        )

        # gpt-4 应该使用特定限制
        usage = await limiter.get_usage("gpt-4")
        assert usage["rpm_limit"] == 5
        assert usage["tpm_limit"] == 500

        # 其他模型应该使用默认限制
        usage = await limiter.get_usage("gpt-3.5-turbo")
        assert usage["rpm_limit"] == 10
        assert usage["tpm_limit"] == 1000

    @pytest.mark.asyncio
    async def test_wait_if_needed(self, limiter: MemoryRateLimiter) -> None:
        """测试等待方法"""
        # 第一个请求不需要等待
        import asyncio

        start = asyncio.get_event_loop().time()
        await limiter.wait_if_needed("gpt-4")
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed < 0.1  # 应该立即返回


class TestModelRateLimits:
    """测试速率限制配置"""

    def test_default_values(self) -> None:
        """测试默认值"""
        limits = ModelRateLimits()
        assert limits.rpm == 60
        assert limits.tpm == 100000

    def test_custom_values(self) -> None:
        """测试自定义值"""
        limits = ModelRateLimits(rpm=100, tpm=200000)
        assert limits.rpm == 100
        assert limits.tpm == 200000
