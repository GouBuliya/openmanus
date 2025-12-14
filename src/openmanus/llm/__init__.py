"""
@PURPOSE: LLM 集成模块，提供多模型适配和策略管理
@OUTLINE:
    - adapters/: LLM 适配器 (base, litellm_adapter, types)
    - PolicyEngine: 模型选择策略
    - ModelRegistry: 模型注册表
    - CostTracker: 成本追踪
    - LLMCache: 响应缓存
    - RateLimiter: 速率限制
    - LLMRouter: 负载均衡和降级
    - LLMTracer: OTel 追踪
    - LLMHealthChecker: 健康检查
@DEPENDENCIES:
    - 外部: litellm, openai, anthropic, redis, opentelemetry
"""

# 适配器
from openmanus.llm.adapters.base import (
    CompletionRequest,
    CompletionResponse,
    ILLMAdapter,
    Message,
    UsageInfo,
)
from openmanus.llm.adapters.litellm_adapter import LiteLLMAdapter
from openmanus.llm.adapters.types import (
    ContentPart,
    ContentType,
    ExtendedCompletionRequest,
    ExtendedCompletionResponse,
    ExtendedMessage,
    ImageDetail,
    ImageUrl,
    StreamChunk,
    Tool,
    ToolCallResponse,
    ToolFunction,
)

# 缓存
from openmanus.llm.cache import (
    LLMCache,
    MemoryLLMCache,
    RedisLLMCache,
    create_cache,
)

# 成本追踪
from openmanus.llm.cost_tracker import CostTracker

# 健康检查
from openmanus.llm.health import (
    HealthCheckResult,
    HealthStatus,
    LLMHealthChecker,
    ModelHealth,
)

# 模型注册表
from openmanus.llm.model_registry import ModelRegistry

# 策略引擎
from openmanus.llm.policy_engine import PolicyEngine

# 速率限制
from openmanus.llm.rate_limiter import (
    MemoryRateLimiter,
    ModelRateLimits,
    RateLimiter,
    RateLimitResult,
    RedisRateLimiter,
)

# 路由器
from openmanus.llm.router import LLMRouter, RouterConfig

# 追踪
from openmanus.llm.tracing import (
    LLMTracer,
    add_llm_attributes,
    create_llm_span,
)

__all__ = [
    # 基础类型
    "Message",
    "CompletionRequest",
    "CompletionResponse",
    "UsageInfo",
    # 扩展类型
    "ContentType",
    "ContentPart",
    "ImageDetail",
    "ImageUrl",
    "Tool",
    "ToolFunction",
    "ToolCallResponse",
    "ExtendedMessage",
    "ExtendedCompletionRequest",
    "ExtendedCompletionResponse",
    "StreamChunk",
    # 适配器
    "ILLMAdapter",
    "LiteLLMAdapter",
    # 缓存
    "LLMCache",
    "RedisLLMCache",
    "MemoryLLMCache",
    "create_cache",
    # 速率限制
    "RateLimiter",
    "RedisRateLimiter",
    "MemoryRateLimiter",
    "ModelRateLimits",
    "RateLimitResult",
    # 路由器
    "LLMRouter",
    "RouterConfig",
    # 策略引擎
    "PolicyEngine",
    # 模型注册表
    "ModelRegistry",
    # 成本追踪
    "CostTracker",
    # 追踪
    "LLMTracer",
    "create_llm_span",
    "add_llm_attributes",
    # 健康检查
    "LLMHealthChecker",
    "HealthStatus",
    "ModelHealth",
    "HealthCheckResult",
]
