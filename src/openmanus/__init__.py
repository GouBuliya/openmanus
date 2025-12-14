"""
OpenManus - AgentScope-based Multi-Agent Execution Platform

一个基于 AgentScope 的多智能体执行平台，提供：
- DAG 拓扑调度
- 契约优先设计
- 资源租约管理
- 多模型 LLM 集成
- 全链路可观测性

Example:
    >>> from openmanus import OpenManus
    >>> manus = OpenManus()
    >>> result = await manus.execute("搜索并总结今日新闻")
"""

__version__ = "0.1.0"
__author__ = "OpenManus Team"

# 延迟导入，避免循环依赖
def __getattr__(name: str):
    if name == "AgentCall":
        from openmanus.core.contracts.agent_call import AgentCall
        return AgentCall
    elif name == "AgentResult":
        from openmanus.core.contracts.agent_result import AgentResult
        return AgentResult
    elif name == "Task":
        from openmanus.core.contracts.task import Task
        return Task
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "__version__",
    "AgentCall",
    "AgentResult",
    "Task",
]
