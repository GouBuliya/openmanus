"""
@PURPOSE: 定义 Agent 调用的标准返回契约
@OUTLINE:
    - enum ResultStatus: 结果状态枚举
    - enum CriticDecision: Critic 决策枚举
    - class EvidenceItem: 证据项
    - class ReplayInfo: 回放信息
    - class ExecutionMetrics: 执行指标
    - class ErrorInfo: 错误信息
    - class CriticFeedback: Critic 反馈
    - class TracingResult: 链路追踪结果
    - class AgentResult: 核心返回契约类
@GOTCHAS:
    - AgentResult 是不可变的 (frozen=True)
    - 使用 success()/failure() 类方法创建结果
@DEPENDENCIES:
    - 外部: pydantic, datetime, enum
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResultStatus(StrEnum):
    """结果状态"""

    SUCCESS = "success"  # 执行成功
    FAILED = "failed"  # 执行失败
    PARTIAL = "partial"  # 部分成功
    TIMEOUT = "timeout"  # 超时
    CANCELLED = "cancelled"  # 被取消
    NEEDS_RETRY = "needs_retry"  # 需要重试
    NEEDS_USER = "needs_user"  # 需要用户介入


class EvidenceItem(BaseModel):
    """证据项"""

    type: str = Field(..., description="证据类型: screenshot, video, dom_snapshot, etc.")
    uri: str = Field(..., description="证据存储 URI (S3/本地路径)")
    content_type: str = Field(default="application/octet-stream", description="MIME 类型")
    size_bytes: int = Field(default=0, ge=0, description="文件大小")
    checksum: str | None = Field(default=None, description="SHA256 校验和")
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = {"frozen": True}


class ReplayInfo(BaseModel):
    """回放信息"""

    replay_uri: str = Field(..., description="回放入口 URI")
    script_url: str | None = Field(default=None, description="可下载的回放脚本 URL")
    artifacts: list[str] = Field(default_factory=list, description="相关工件 URI 列表")
    format: str = Field(default="openmanus-replay-v1", description="回放格式版本")

    model_config = {"frozen": True}


class ExecutionMetrics(BaseModel):
    """执行指标"""

    # 时间指标
    duration_ms: int = Field(default=0, ge=0, description="总执行时间(毫秒)")
    queue_wait_ms: int = Field(default=0, ge=0, description="队列等待时间(毫秒)")
    llm_latency_ms: int = Field(default=0, ge=0, description="LLM 调用时间(毫秒)")

    # LLM 指标
    prompt_tokens: int = Field(default=0, ge=0, description="Prompt Token 数")
    completion_tokens: int = Field(default=0, ge=0, description="Completion Token 数")
    total_tokens: int = Field(default=0, ge=0, description="总 Token 数")

    # 成本指标
    cost_usd: float = Field(default=0.0, ge=0.0, description="LLM 成本(美元)")

    # 重试指标
    retry_count: int = Field(default=0, ge=0, description="重试次数")

    # 模型信息
    model_used: str | None = Field(default=None, description="实际使用的模型")

    model_config = {"frozen": True}


class ErrorInfo(BaseModel):
    """错误信息"""

    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误消息")
    category: str = Field(
        default="unknown",
        description="错误类别: validation, execution, timeout, resource, llm",
    )
    retryable: bool = Field(default=False, description="是否可重试")
    details: dict[str, Any] = Field(default_factory=dict, description="详细信息")
    stack_trace: str | None = Field(default=None, description="堆栈跟踪")

    model_config = {"frozen": True}


class CriticDecision(StrEnum):
    """Critic 决策"""

    ACCEPT = "accept"  # 接受结果
    RETRY = "retry"  # 重试
    SWITCH_RESOURCE = "switch_resource"  # 切换资源
    REPLAN = "replan"  # 重新规划
    NEEDS_USER = "needs_user"  # 需要用户介入


class CriticFeedback(BaseModel):
    """Critic 反馈"""

    decision: CriticDecision = Field(..., description="决策")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reasoning: str = Field(default="", description="决策理由")
    suggestions: list[str] = Field(default_factory=list, description="改进建议")

    model_config = {"frozen": True}


class TracingResult(BaseModel):
    """链路追踪结果"""

    task_id: str = Field(..., description="任务 ID")
    step_id: str = Field(..., description="步骤 ID")
    call_id: str = Field(..., description="调用 ID")
    trace_id: str | None = Field(default=None)
    span_id: str | None = Field(default=None)

    model_config = {"frozen": True}


class AgentResult(BaseModel):
    """
    AgentResult - Agent 调用的标准返回格式

    所有 Agent 执行完成后必须返回此格式的结果。

    Example:
        >>> result = AgentResult(
        ...     status=ResultStatus.SUCCESS,
        ...     outputs={"products": [{"title": "iPhone 15", "price": 5999}]},
        ...     evidence=[
        ...         EvidenceItem(type="screenshot", uri="s3://bucket/screenshot.png"),
        ...     ],
        ...     metrics=ExecutionMetrics(duration_ms=5000, cost_usd=0.02),
        ...     replay=ReplayInfo(replay_uri="https://replay.example.com/abc"),
        ...     tracing=TracingResult(
        ...         task_id="task_abc",
        ...         step_id="step_001",
        ...         call_id="call_xyz",
        ...     ),
        ... )
    """

    # =========================================================================
    # 状态
    # =========================================================================
    status: ResultStatus = Field(..., description="执行状态")

    # =========================================================================
    # 输出
    # =========================================================================
    outputs: dict[str, Any] = Field(default_factory=dict, description="结构化输出")
    raw_output: str | None = Field(default=None, description="原始输出文本")

    # =========================================================================
    # 证据
    # =========================================================================
    evidence: list[EvidenceItem] = Field(default_factory=list, description="证据列表")
    action_log: list[dict[str, Any]] = Field(default_factory=list, description="操作日志")

    # =========================================================================
    # 指标
    # =========================================================================
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)

    # =========================================================================
    # 回放
    # =========================================================================
    replay: ReplayInfo | None = Field(default=None, description="回放信息")

    # =========================================================================
    # 错误信息
    # =========================================================================
    error: ErrorInfo | None = Field(default=None, description="错误信息 (失败时)")

    # =========================================================================
    # Critic 反馈
    # =========================================================================
    critic_feedback: CriticFeedback | None = Field(default=None, description="Critic 反馈")

    # =========================================================================
    # 链路追踪
    # =========================================================================
    tracing: TracingResult = Field(..., description="链路追踪")

    # =========================================================================
    # 元数据
    # =========================================================================
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self.status == ResultStatus.SUCCESS

    @property
    def is_retryable(self) -> bool:
        """是否可重试"""
        if self.status == ResultStatus.NEEDS_RETRY:
            return True
        if self.error and self.error.retryable:
            return True
        if self.critic_feedback and self.critic_feedback.decision == CriticDecision.RETRY:
            return True
        return False

    @classmethod
    def success(
        cls,
        outputs: dict[str, Any],
        tracing: TracingResult,
        evidence: list[EvidenceItem] | None = None,
        metrics: ExecutionMetrics | None = None,
        replay: ReplayInfo | None = None,
    ) -> "AgentResult":
        """创建成功结果的便捷方法"""
        return cls(
            status=ResultStatus.SUCCESS,
            outputs=outputs,
            evidence=evidence or [],
            metrics=metrics or ExecutionMetrics(),
            replay=replay,
            tracing=tracing,
        )

    @classmethod
    def failure(
        cls,
        error: ErrorInfo,
        tracing: TracingResult,
        outputs: dict[str, Any] | None = None,
        evidence: list[EvidenceItem] | None = None,
        metrics: ExecutionMetrics | None = None,
    ) -> "AgentResult":
        """创建失败结果的便捷方法"""
        return cls(
            status=ResultStatus.FAILED,
            outputs=outputs or {},
            error=error,
            evidence=evidence or [],
            metrics=metrics or ExecutionMetrics(),
            tracing=tracing,
        )
