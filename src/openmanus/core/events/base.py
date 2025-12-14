"""
@PURPOSE: 定义领域事件基类，遵循 CloudEvents 规范
@OUTLINE:
    - class DomainEvent: 领域事件基类，包含 event_id, event_type, timestamp 等
@DEPENDENCIES:
    - 外部: pydantic, datetime, uuid
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """
    领域事件基类

    所有领域事件必须继承此类。
    遵循 CloudEvents 规范 (简化版)。

    Example:
        >>> class TaskCreatedEvent(DomainEvent):
        ...     event_type: str = "task.created"
        ...     task_id: str
        ...     tenant_id: str
    """

    # =========================================================================
    # CloudEvents 标准字段
    # =========================================================================
    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid4().hex[:12]}",
        description="事件唯一 ID",
    )
    event_type: str = Field(..., description="事件类型，格式: {domain}.{action}")
    source: str = Field(default="openmanus", description="事件来源")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="事件时间")

    # =========================================================================
    # 追踪字段
    # =========================================================================
    trace_id: str | None = Field(default=None, description="OpenTelemetry trace_id")
    span_id: str | None = Field(default=None, description="OpenTelemetry span_id")

    # =========================================================================
    # 聚合根
    # =========================================================================
    aggregate_id: str | None = Field(default=None, description="聚合根 ID (如 task_id)")
    aggregate_type: str | None = Field(default=None, description="聚合根类型 (如 Task)")

    # =========================================================================
    # 序列号 (用于事件溯源)
    # =========================================================================
    sequence: int = Field(default=0, ge=0, description="事件序列号")

    # =========================================================================
    # 元数据
    # =========================================================================
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    def to_cloud_event(self) -> dict[str, Any]:
        """
        转换为 CloudEvents 格式

        Returns:
            CloudEvents JSON 格式
        """
        return {
            "specversion": "1.0",
            "id": self.event_id,
            "type": self.event_type,
            "source": self.source,
            "time": self.timestamp.isoformat() + "Z",
            "datacontenttype": "application/json",
            "data": self.model_dump(exclude={"event_id", "event_type", "source", "timestamp"}),
        }
