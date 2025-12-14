"""
@PURPOSE: 定义 Agent 的标准接口协议
@OUTLINE:
    - protocol IAgent: Agent 核心接口 (agent_id, capabilities, invoke)
    - protocol IAgentRegistry: Agent 注册表接口
    - protocol IAgentFactory: Agent 工厂接口
    - protocol IAgentRouter: Agent 路由器接口
@DEPENDENCIES:
    - 内部: openmanus.core.contracts.agent_call, agent_result
    - 外部: typing.Protocol
"""

from typing import Protocol, runtime_checkable

from openmanus.core.contracts.agent_call import AgentCall
from openmanus.core.contracts.agent_result import AgentResult


@runtime_checkable
class IAgent(Protocol):
    """
    Agent 接口协议

    所有 Agent 必须实现此接口。
    使用 Protocol 支持鸭子类型，无需显式继承。

    Example:
        >>> class MyAgent:
        ...     @property
        ...     def agent_id(self) -> str:
        ...         return "my_agent"
        ...
        ...     @property
        ...     def capabilities(self) -> list[str]:
        ...         return ["my.capability"]
        ...
        ...     @property
        ...     def requires_lease(self) -> bool:
        ...         return False
        ...
        ...     async def invoke(self, call: AgentCall) -> AgentResult:
        ...         ...
        ...
        >>> assert isinstance(MyAgent(), IAgent)
    """

    @property
    def agent_id(self) -> str:
        """Agent 唯一标识，格式: {domain}.{role}"""
        ...

    @property
    def capabilities(self) -> list[str]:
        """Agent 支持的能力列表，格式: {domain}.{action}"""
        ...

    @property
    def requires_lease(self) -> bool:
        """是否需要资源租约"""
        ...

    async def invoke(self, call: AgentCall) -> AgentResult:
        """
        调用 Agent 执行任务

        Args:
            call: AgentCall 契约，包含意图、返回规格、成功标准等

        Returns:
            AgentResult 契约，包含状态、输出、证据、指标等

        Raises:
            AgentExecutionError: 执行失败
            LeaseError: 租约无效 (仅执行类 Agent)
        """
        ...


@runtime_checkable
class IAgentRegistry(Protocol):
    """
    Agent 注册表接口

    管理 Agent 的注册和发现。
    """

    def register(self, agent: IAgent) -> None:
        """注册 Agent"""
        ...

    def unregister(self, agent_id: str) -> None:
        """注销 Agent"""
        ...

    def get(self, agent_id: str) -> IAgent | None:
        """根据 ID 获取 Agent"""
        ...

    def find_by_capability(self, capability: str) -> list[IAgent]:
        """根据能力查找 Agent"""
        ...

    def list_all(self) -> list[IAgent]:
        """列出所有 Agent"""
        ...

    def list_capabilities(self) -> list[str]:
        """列出所有已注册的能力"""
        ...


@runtime_checkable
class IAgentFactory(Protocol):
    """
    Agent 工厂接口

    根据能力创建 Agent 实例。
    """

    def create(self, capability: str) -> IAgent:
        """
        根据能力创建 Agent

        Args:
            capability: 所需能力

        Returns:
            符合能力的 Agent 实例

        Raises:
            AgentNotFoundError: 未找到符合能力的 Agent
        """
        ...

    def create_by_id(self, agent_id: str) -> IAgent:
        """
        根据 ID 创建 Agent

        Args:
            agent_id: Agent ID

        Returns:
            Agent 实例

        Raises:
            AgentNotFoundError: 未找到指定 Agent
        """
        ...


@runtime_checkable
class IAgentRouter(Protocol):
    """
    Agent 路由器接口

    根据 AgentCall 路由到最合适的 Agent。
    """

    async def route(self, call: AgentCall, capability: str) -> IAgent:
        """
        路由到最合适的 Agent

        Args:
            call: AgentCall 契约
            capability: 所需能力

        Returns:
            最合适的 Agent 实例

        考虑因素:
        - 能力匹配度
        - Agent 负载
        - 历史成功率
        - 资源亲和性
        """
        ...
