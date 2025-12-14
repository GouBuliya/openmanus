"""
OpenManus 接口协议模块

使用 typing.Protocol 定义所有核心接口，支持鸭子类型。
这些接口是依赖注入和模块解耦的基础。
"""

from openmanus.core.interfaces.agent import IAgent, IAgentFactory, IAgentRegistry
from openmanus.core.interfaces.event_bus import IEventBus, IEventHandler
from openmanus.core.interfaces.lease_manager import ILeaseManager
from openmanus.core.interfaces.repository import IRepository
from openmanus.core.interfaces.scheduler import IScheduler

__all__ = [
    "IAgent",
    "IAgentRegistry",
    "IAgentFactory",
    "IScheduler",
    "ILeaseManager",
    "IRepository",
    "IEventBus",
    "IEventHandler",
]
