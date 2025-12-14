"""
@PURPOSE: 定义 Task 生命周期相关的领域事件
@OUTLINE:
    - TaskCreatedEvent: 任务创建
    - TaskStartedEvent: 任务开始
    - TaskCompletedEvent: 任务完成
    - TaskFailedEvent: 任务失败
    - TaskCancelledEvent: 任务取消
    - TaskPausedEvent: 任务暂停
    - TaskResumedEvent: 任务恢复
@DEPENDENCIES:
    - 内部: openmanus.core.events.base
"""

from typing import Any

from pydantic import Field

from openmanus.core.events.base import DomainEvent


class TaskCreatedEvent(DomainEvent):
    """任务创建事件"""

    event_type: str = "task.created"
    aggregate_type: str = "Task"

    task_id: str = Field(..., description="任务 ID")
    tenant_id: str = Field(..., description="租户 ID")
    user_input: str = Field(..., description="用户输入")


class TaskStartedEvent(DomainEvent):
    """任务开始事件"""

    event_type: str = "task.started"
    aggregate_type: str = "Task"

    task_id: str
    step_count: int = Field(default=0, description="步骤总数")


class TaskCompletedEvent(DomainEvent):
    """任务完成事件"""

    event_type: str = "task.completed"
    aggregate_type: str = "Task"

    task_id: str
    success: bool
    duration_ms: int = Field(default=0)
    total_cost_usd: float = Field(default=0.0)
    outputs: dict[str, Any] = Field(default_factory=dict)


class TaskFailedEvent(DomainEvent):
    """任务失败事件"""

    event_type: str = "task.failed"
    aggregate_type: str = "Task"

    task_id: str
    error_code: str
    error_message: str
    failed_step_id: str | None = None


class TaskCancelledEvent(DomainEvent):
    """任务取消事件"""

    event_type: str = "task.cancelled"
    aggregate_type: str = "Task"

    task_id: str
    reason: str = ""
    cancelled_by: str | None = None  # user_id 或 system


class TaskPausedEvent(DomainEvent):
    """任务暂停事件"""

    event_type: str = "task.paused"
    aggregate_type: str = "Task"

    task_id: str
    reason: str = ""


class TaskResumedEvent(DomainEvent):
    """任务恢复事件"""

    event_type: str = "task.resumed"
    aggregate_type: str = "Task"

    task_id: str
