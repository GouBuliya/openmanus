"""
LiteLLM 适配器单元测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmanus.config.settings import LLMSettings
from openmanus.core.exceptions import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from openmanus.llm.adapters.base import CompletionRequest, Message
from openmanus.llm.adapters.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def mock_settings() -> LLMSettings:
    """创建测试配置"""
    return LLMSettings(
        default_model="gpt-4",
        openai_api_key="test-key",
        max_retries=3,
        timeout_seconds=60,
    )


@pytest.fixture
def adapter(mock_settings: LLMSettings) -> LiteLLMAdapter:
    """创建适配器实例"""
    return LiteLLMAdapter(settings=mock_settings)


@pytest.fixture
def sample_request() -> CompletionRequest:
    """创建示例请求"""
    return CompletionRequest(
        model="gpt-4",
        messages=[
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello!"),
        ],
        temperature=0.7,
        max_tokens=100,
    )


class TestLiteLLMAdapterInit:
    """测试适配器初始化"""

    def test_init_with_default_settings(self) -> None:
        """测试使用默认配置初始化"""
        with patch("openmanus.llm.adapters.litellm_adapter.get_settings") as mock_get:
            mock_get.return_value.llm = LLMSettings()
            adapter = LiteLLMAdapter()
            assert adapter._settings.default_model == "gpt-4"

    def test_init_with_custom_settings(self, mock_settings: LLMSettings) -> None:
        """测试使用自定义配置初始化"""
        adapter = LiteLLMAdapter(settings=mock_settings)
        assert adapter._settings.openai_api_key == "test-key"

    def test_init_with_cache(self, mock_settings: LLMSettings) -> None:
        """测试使用缓存初始化"""
        mock_cache = MagicMock()
        adapter = LiteLLMAdapter(settings=mock_settings, cache=mock_cache)
        assert adapter._cache is mock_cache


class TestLiteLLMAdapterComplete:
    """测试 complete 方法"""

    @pytest.mark.asyncio
    async def test_complete_success(
        self, adapter: LiteLLMAdapter, sample_request: CompletionRequest
    ) -> None:
        """测试成功完成请求"""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="Hello! How can I help you?"),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10, completion_tokens=20, total_tokens=30
        )
        mock_response.model = "gpt-4"

        with (
            patch.object(adapter, "_execute_with_retry", new_callable=AsyncMock) as mock_exec,
            patch("openmanus.llm.adapters.litellm_adapter.completion_cost", return_value=0.001),
        ):
            mock_exec.return_value = mock_response
            response = await adapter.complete(sample_request)

            assert response.content == "Hello! How can I help you?"
            assert response.model == "gpt-4"
            assert response.usage.total_tokens == 30
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_complete_with_cache_hit(
        self, mock_settings: LLMSettings, sample_request: CompletionRequest
    ) -> None:
        """测试缓存命中"""
        from openmanus.llm.adapters.base import CompletionResponse, UsageInfo

        mock_cache = AsyncMock()
        cached_response = CompletionResponse(
            content="Cached response",
            model="gpt-4",
            usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
        )
        mock_cache.get.return_value = cached_response

        adapter = LiteLLMAdapter(settings=mock_settings, cache=mock_cache)
        response = await adapter.complete(sample_request)

        assert response.content == "Cached response"
        mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_rate_limit_error(
        self, adapter: LiteLLMAdapter, sample_request: CompletionRequest
    ) -> None:
        """测试速率限制错误"""
        from litellm.exceptions import RateLimitError

        with patch.object(adapter, "_execute_with_retry", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RateLimitError(
                "Rate limit exceeded", llm_provider="openai", model="gpt-4"
            )

            with pytest.raises(LLMRateLimitError):
                await adapter.complete(sample_request)

    @pytest.mark.asyncio
    async def test_complete_timeout_error(
        self, adapter: LiteLLMAdapter, sample_request: CompletionRequest
    ) -> None:
        """测试超时错误"""
        from litellm.exceptions import Timeout

        with patch.object(adapter, "_execute_with_retry", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Timeout(
                "Request timeout", llm_provider="openai", model="gpt-4"
            )

            with pytest.raises(LLMTimeoutError):
                await adapter.complete(sample_request)


class TestLiteLLMAdapterStreamComplete:
    """测试 stream_complete 方法"""

    @pytest.mark.asyncio
    async def test_stream_complete_success(
        self, adapter: LiteLLMAdapter, sample_request: CompletionRequest
    ) -> None:
        """测试流式完成请求"""

        async def mock_stream():
            chunks = ["Hello", " ", "World", "!"]
            for chunk in chunks:
                mock_chunk = MagicMock()
                mock_chunk.choices = [MagicMock(delta=MagicMock(content=chunk))]
                yield mock_chunk

        with patch(
            "openmanus.llm.adapters.litellm_adapter.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.return_value = mock_stream()

            result = []
            async for chunk in adapter.stream_complete(sample_request):
                result.append(chunk)

            assert "".join(result) == "Hello World!"


class TestLiteLLMAdapterHealthCheck:
    """测试 health_check 方法"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter: LiteLLMAdapter) -> None:
        """测试健康检查成功"""
        mock_response = MagicMock()

        with patch(
            "openmanus.llm.adapters.litellm_adapter.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.return_value = mock_response
            result = await adapter.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, adapter: LiteLLMAdapter) -> None:
        """测试健康检查失败"""
        with patch(
            "openmanus.llm.adapters.litellm_adapter.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = Exception("Connection failed")
            result = await adapter.health_check()
            assert result is False


class TestLiteLLMAdapterTokenEstimation:
    """测试 Token 估算方法"""

    def test_estimate_tokens(self, adapter: LiteLLMAdapter) -> None:
        """测试 Token 估算"""
        messages = [
            Message(role="user", content="Hello world"),
            Message(role="assistant", content="Hi there"),
        ]

        with patch(
            "openmanus.llm.adapters.litellm_adapter.token_counter", return_value=10
        ) as mock_counter:
            result = adapter.estimate_tokens(messages)
            assert result == 10
            mock_counter.assert_called_once()

    def test_estimate_cost(self, adapter: LiteLLMAdapter) -> None:
        """测试成本估算"""
        with patch(
            "litellm.cost_per_token",
            return_value=(0.001, 0.002),
        ):
            result = adapter.estimate_cost("gpt-4", 100, 50)
            assert result == 0.003


class TestLiteLLMAdapterSupportedModels:
    """测试支持的模型列表"""

    def test_get_supported_models(self, adapter: LiteLLMAdapter) -> None:
        """测试获取支持的模型列表"""
        models = adapter.get_supported_models()
        assert "gpt-4" in models
        assert "claude-3-opus-20240229" in models
        assert "deepseek/deepseek-chat" in models

    def test_supported_models_is_copy(self, adapter: LiteLLMAdapter) -> None:
        """测试返回的是列表副本"""
        models1 = adapter.get_supported_models()
        models2 = adapter.get_supported_models()
        assert models1 is not models2
