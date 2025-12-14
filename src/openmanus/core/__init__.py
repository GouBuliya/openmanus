"""
OpenManus 核心模块

包含：
- contracts: Pydantic 契约模型
- interfaces: 协议接口定义
- events: 领域事件
- types: 通用类型别名
- exceptions: 领域异常
"""

__all__ = [
    "AgentCall",
    "AgentResult",
    "OpenManusError",
    "TaskId",
    "StepId",
    "LeaseId",
    "AgentId",
]

def __getattr__(name: str):
    if name in ("AgentCall", "AgentResult"):
        from openmanus.core import contracts
        return getattr(contracts, name)
    elif name == "OpenManusError":
        from openmanus.core.exceptions import OpenManusError
        return OpenManusError
    elif name in ("TaskId", "StepId", "LeaseId", "AgentId"):
        from openmanus.core import types as core_types
        return getattr(core_types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
