"""
@PURPOSE: 定义 Agent 调用的标准请求契约，是平台核心契约
@OUTLINE:
    - enum RiskLevel: 风险等级枚举 (low/medium/high/critical)
    - enum VerificationMode: 验证模式枚举 (single/voting/adversarial)
    - class ReturnSpec: 返回规格定义
    - class SuccessCriteria: 成功标准定义
    - class RetryPolicy: 重试策略
    - class ModelProfile: LLM 模型配置
    - class Constraints: 约束条件
    - class ExecutionConfig: 执行配置
    - class VerificationConfig: 验证配置
    - class TracingContext: 链路追踪上下文
    - class MemoryContext: 记忆上下文
    - class AgentCall: 核心契约类
@GOTCHAS:
    - AgentCall 是不可变的 (frozen=True)
    - 执行类 Agent 的 lease_id 在运行时注入
    - 使用 with_* 方法创建修改后的副本
@DEPENDENCIES:
    - 外部: pydantic, datetime, enum
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


class RiskLevel(StrEnum):
    """风险等级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VerificationMode(StrEnum):
    """验证模式"""

    SINGLE = "single"  # 单 Agent 执行 + Critic 验证
    VOTING = "voting"  # 多 Agent 投票
    ADVERSARIAL = "adversarial"  # 对抗验证


class ReturnSpec(BaseModel):
    """返回规格 - 定义 Agent 应该返回什么"""

    schema_id: str = Field(..., description="输出 Schema 标识符")
    required_fields: list[str] = Field(default_factory=list, description="必需字段")
    optional_fields: list[str] = Field(default_factory=list, description="可选字段")
    format: str = Field(default="json", description="返回格式: json/text/binary")

    model_config = {"frozen": True}


class SuccessCriteria(BaseModel):
    """成功标准 - 定义如何判断执行成功"""

    conditions: list[str] = Field(..., description="成功条件列表 (AND 关系)")
    timeout_ms: int = Field(default=30000, ge=1000, le=600000, description="超时时间(毫秒)")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")

    model_config = {"frozen": True}


class RetryPolicy(BaseModel):
    """重试策略"""

    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_ms: int = Field(default=1000, ge=100)
    max_delay_ms: int = Field(default=30000, ge=1000)
    exponential_base: float = Field(default=2.0, ge=1.0, le=4.0)
    retryable_errors: list[str] = Field(
        default_factory=lambda: ["timeout", "rate_limit", "transient"]
    )

    model_config = {"frozen": True}


class ModelProfile(BaseModel):
    """模型配置 - LLM 选择策略"""

    preferred_models: list[str] = Field(
        default_factory=lambda: ["gpt-4o", "claude-3-sonnet"],
        description="首选模型列表",
    )
    fallback_models: list[str] = Field(
        default_factory=lambda: ["gpt-4o-mini", "claude-3-haiku"],
        description="降级模型列表",
    )
    max_cost_per_call_usd: float = Field(default=0.1, ge=0.0, le=10.0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)

    model_config = {"frozen": True}


class Constraints(BaseModel):
    """约束条件 - 限制 Agent 的行为边界"""

    # 域名限制
    allowed_domains: list[str] = Field(default_factory=list, description="允许的域名")
    forbidden_domains: list[str] = Field(default_factory=list, description="禁止的域名")

    # 操作限制
    allowed_actions: list[str] = Field(default_factory=list, description="允许的操作")
    forbidden_actions: list[str] = Field(default_factory=list, description="禁止的操作")

    # 资源限制
    time_budget_ms: int = Field(default=300000, ge=1000, le=3600000, description="时间预算(毫秒)")
    cost_budget_usd: float = Field(default=1.0, ge=0.0, le=100.0, description="成本预算(美元)")
    token_budget: int = Field(default=100000, ge=100, le=10000000, description="Token 预算")

    # 安全限制
    secrets_scope: str | None = Field(default=None, description="Secret 作用域")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="风险等级")
    requires_human_approval: bool = Field(default=False, description="是否需要人工审批")

    # 行为标志
    no_purchase: bool = Field(default=True, description="禁止购买操作")
    no_external_api: bool = Field(default=False, description="禁止外部 API 调用")
    dry_run: bool = Field(default=False, description="干跑模式（不执行副作用）")

    model_config = {"frozen": True}


class ExecutionConfig(BaseModel):
    """执行配置"""

    lease_id: str | None = Field(default=None, description="租约 ID (执行 Agent 必需)")
    model_profile: ModelProfile = Field(default_factory=ModelProfile)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)

    # 资源提示
    preferred_resource_labels: dict[str, str] = Field(
        default_factory=dict,
        description="首选资源标签 (K8s 风格)",
    )

    model_config = {"frozen": True}


class VerificationConfig(BaseModel):
    """验证配置"""

    mode: VerificationMode = Field(default=VerificationMode.SINGLE)

    # 投票模式配置
    voting_models: list[str] = Field(
        default_factory=lambda: ["gpt-4o", "claude-3-sonnet", "deepseek-chat"],
    )
    min_agreement_ratio: float = Field(default=0.67, ge=0.5, le=1.0)

    # 对抗模式配置
    challenger_model: str = Field(default="claude-3-opus")
    arbiter_model: str = Field(default="gpt-4o")

    model_config = {"frozen": True}


class TracingContext(BaseModel):
    """链路追踪上下文"""

    task_id: str = Field(..., description="任务 ID")
    step_id: str = Field(..., description="步骤 ID")
    call_id: str = Field(..., description="调用 ID")
    parent_call_id: str | None = Field(default=None, description="父调用 ID")
    trace_id: str | None = Field(default=None, description="OpenTelemetry trace_id")
    span_id: str | None = Field(default=None, description="OpenTelemetry span_id")

    model_config = {"frozen": True}


class MemoryContext(BaseModel):
    """记忆上下文 - 由编排器自动注入"""

    similar_tasks: list[dict[str, Any]] = Field(default_factory=list, description="相似任务")
    site_profile: dict[str, Any] = Field(default_factory=dict, description="站点画像")
    known_issues: list[dict[str, Any]] = Field(default_factory=list, description="已知问题")
    recommended_strategies: list[str] = Field(default_factory=list, description="推荐策略")

    model_config = {"frozen": True}


class AgentCall(BaseModel):
    """
    AgentCall - Agent 调用的标准请求格式

    这是 OpenManus 的核心契约，所有 Agent 调用都必须符合此格式。

    Example:
        >>> call = AgentCall(
        ...     intent="在淘宝搜索 iPhone 15 并获取前5个商品信息",
        ...     return_spec=ReturnSpec(
        ...         schema_id="product_list",
        ...         required_fields=["title", "price", "url"],
        ...     ),
        ...     success_criteria=SuccessCriteria(
        ...         conditions=["返回至少1个商品", "所有商品包含价格"],
        ...     ),
        ...     evidence_required=["screenshot", "dom_snapshot"],
        ...     tracing=TracingContext(
        ...         task_id="task_abc123",
        ...         step_id="step_001",
        ...         call_id="call_xyz",
        ...     ),
        ... )
    """

    # =========================================================================
    # 核心意图
    # =========================================================================
    intent: str = Field(..., min_length=1, max_length=10000, description="自然语言意图描述")
    intent_structured: dict[str, Any] | None = Field(
        default=None,
        description="结构化意图 (可选)",
    )

    # =========================================================================
    # 输出要求
    # =========================================================================
    return_spec: ReturnSpec = Field(..., description="返回规格")
    success_criteria: SuccessCriteria = Field(..., description="成功标准")
    evidence_required: list[str] = Field(
        default_factory=list,
        description="所需证据类型: screenshot, video, dom_snapshot, etc.",
    )

    # =========================================================================
    # 上下文 (由编排器自动注入)
    # =========================================================================
    upstream_results: dict[str, Any] = Field(
        default_factory=dict,
        description="上游步骤结果 (DAG 依赖注入)",
    )
    memory_context: MemoryContext = Field(
        default_factory=MemoryContext,
        description="记忆上下文",
    )
    user_context: str | None = Field(default=None, description="用户上下文")
    session_context: dict[str, Any] = Field(default_factory=dict, description="会话上下文")

    # =========================================================================
    # 约束与策略
    # =========================================================================
    constraints: Constraints = Field(default_factory=Constraints)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)

    # =========================================================================
    # 链路追踪
    # =========================================================================
    tracing: TracingContext = Field(..., description="链路追踪上下文")

    # =========================================================================
    # 元数据
    # =========================================================================
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_execution_agent_has_lease(self) -> Self:
        """执行类 Agent 必须有 lease_id (由调用方保证)"""
        # 注意: 这里不强制验证，因为 lease_id 可能在运行时注入
        return self

    def with_upstream_results(self, results: dict[str, Any]) -> "AgentCall":
        """注入上游结果，返回新的 AgentCall"""
        return self.model_copy(update={"upstream_results": results})

    def with_memory_context(self, memory: MemoryContext) -> "AgentCall":
        """注入记忆上下文，返回新的 AgentCall"""
        return self.model_copy(update={"memory_context": memory})

    def with_lease(self, lease_id: str) -> "AgentCall":
        """注入租约 ID，返回新的 AgentCall"""
        new_execution = self.execution.model_copy(update={"lease_id": lease_id})
        return self.model_copy(update={"execution": new_execution})
