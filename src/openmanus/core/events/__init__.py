"""
OpenManus 领域事件模块

定义平台使用的所有领域事件。
"""

from openmanus.core.events.base import DomainEvent
from openmanus.core.events.step_events import (
    StepCompletedEvent,
    StepFailedEvent,
    StepStartedEvent,
)
from openmanus.core.events.task_events import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)

__all__ = [
    "DomainEvent",
    # Task events
    "TaskCreatedEvent",
    "TaskStartedEvent",
    "TaskCompletedEvent",
    "TaskFailedEvent",
    "TaskCancelledEvent",
    # Step events
    "StepStartedEvent",
    "StepCompletedEvent",
    "StepFailedEvent",
]
