"""
@PURPOSE: 定义 Step 和 Lease 相关的领域事件
@OUTLINE:
    - StepStartedEvent: 步骤开始
    - StepCompletedEvent: 步骤完成
    - StepFailedEvent: 步骤失败
    - StepRetryingEvent: 步骤重试
    - LeaseAcquiredEvent: 租约获取
    - LeaseReleasedEvent: 租约释放
    - LeaseExpiredEvent: 租约过期
@DEPENDENCIES:
    - 内部: openmanus.core.events.base
"""

from typing import Any

from pydantic import Field

from openmanus.core.events.base import DomainEvent


class StepStartedEvent(DomainEvent):
    """步骤开始事件"""

    event_type: str = "step.started"
    aggregate_type: str = "Step"

    task_id: str
    step_id: str
    step_name: str
    capability: str
    lease_id: str | None = None


class StepCompletedEvent(DomainEvent):
    """步骤完成事件"""

    event_type: str = "step.completed"
    aggregate_type: str = "Step"

    task_id: str
    step_id: str
    success: bool
    duration_ms: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    outputs: dict[str, Any] = Field(default_factory=dict)


class StepFailedEvent(DomainEvent):
    """步骤失败事件"""

    event_type: str = "step.failed"
    aggregate_type: str = "Step"

    task_id: str
    step_id: str
    error_code: str
    error_message: str
    retry_count: int = Field(default=0)
    retryable: bool = Field(default=False)


class StepRetryingEvent(DomainEvent):
    """步骤重试事件"""

    event_type: str = "step.retrying"
    aggregate_type: str = "Step"

    task_id: str
    step_id: str
    retry_count: int
    max_retries: int
    reason: str = ""


class LeaseAcquiredEvent(DomainEvent):
    """租约获取事件"""

    event_type: str = "lease.acquired"
    aggregate_type: str = "Lease"

    lease_id: str
    resource_id: str
    task_id: str
    step_id: str
    expires_at: str  # ISO format


class LeaseReleasedEvent(DomainEvent):
    """租约释放事件"""

    event_type: str = "lease.released"
    aggregate_type: str = "Lease"

    lease_id: str
    resource_id: str
    task_id: str
    step_id: str
    duration_ms: int = Field(default=0)


class LeaseExpiredEvent(DomainEvent):
    """租约过期事件"""

    event_type: str = "lease.expired"
    aggregate_type: str = "Lease"

    lease_id: str
    resource_id: str
    task_id: str
    step_id: str
