"""
@PURPOSE: 定义事件总线接口协议
@OUTLINE:
    - protocol IEventHandler: 事件处理器接口
    - protocol IEventBus: 事件总线接口 (subscribe, publish)
    - protocol IEventStore: 事件存储接口 (用于审计和重放)
@DEPENDENCIES:
    - 内部: openmanus.core.events.base
    - 外部: typing.Protocol
"""

from typing import Any, Callable, Protocol, runtime_checkable

from openmanus.core.events.base import DomainEvent


@runtime_checkable
class IEventHandler(Protocol):
    """
    事件处理器接口
    """

    async def handle(self, event: DomainEvent) -> None:
        """
        处理事件

        Args:
            event: 领域事件
        """
        ...


# 事件处理器类型别名
EventHandler = Callable[[DomainEvent], Any]


@runtime_checkable
class IEventBus(Protocol):
    """
    事件总线接口

    提供发布/订阅模式的事件通信。
    支持同步和异步事件处理。

    Example:
        >>> bus = InMemoryEventBus()
        >>> bus.subscribe("task.created", my_handler)
        >>> await bus.publish(TaskCreatedEvent(task_id="task_001"))
    """

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> Callable[[], None]:
        """
        订阅事件

        Args:
            event_type: 事件类型，支持通配符 (如 "task.*")
            handler: 事件处理函数

        Returns:
            取消订阅的函数
        """
        ...

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """
        取消订阅

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        ...

    async def publish(self, event: DomainEvent) -> None:
        """
        发布事件

        Args:
            event: 领域事件

        事件会被分发给所有匹配的订阅者。
        """
        ...

    async def publish_many(self, events: list[DomainEvent]) -> None:
        """
        批量发布事件

        Args:
            events: 事件列表
        """
        ...


@runtime_checkable
class IEventStore(Protocol):
    """
    事件存储接口

    持久化存储事件，用于审计和重放。
    """

    async def append(self, event: DomainEvent) -> None:
        """
        追加事件

        Args:
            event: 领域事件
        """
        ...

    async def get_events(
        self,
        aggregate_id: str,
        after_sequence: int = 0,
    ) -> list[DomainEvent]:
        """
        获取聚合根的事件

        Args:
            aggregate_id: 聚合根 ID (如 task_id)
            after_sequence: 从此序列号之后开始

        Returns:
            事件列表
        """
        ...

    async def get_events_by_type(
        self,
        event_type: str,
        limit: int = 100,
    ) -> list[DomainEvent]:
        """
        根据类型获取事件

        Args:
            event_type: 事件类型
            limit: 最大数量

        Returns:
            事件列表
        """
        ...
