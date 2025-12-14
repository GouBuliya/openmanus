"""
@PURPOSE: 定义 DAG 调度器接口协议
@OUTLINE:
    - protocol IScheduler: DAG 调度器接口 (topological_sort, get_ready_steps)
    - protocol IStepExecutor: 步骤执行器接口
    - protocol IOrchestrator: 编排器接口
@GOTCHAS:
    - 调度算法使用分层 Kahn 算法，时间复杂度 O(V+E)
@DEPENDENCIES:
    - 内部: openmanus.core.contracts.step
    - 外部: typing.Protocol
"""

from typing import Any, Protocol, runtime_checkable

from openmanus.core.contracts.step import Step, StepResult


@runtime_checkable
class IScheduler(Protocol):
    """
    DAG 调度器接口

    负责:
    - DAG 拓扑排序
    - 分层并行调度
    - 依赖管理
    - 失败处理

    调度算法: 分层 Kahn 算法
    时间复杂度: O(V + E)
    """

    def topological_sort(self, steps: list[Step]) -> list[list[str]]:
        """
        DAG 拓扑排序

        Args:
            steps: 步骤列表

        Returns:
            分层的步骤 ID 列表: [[level0_ids], [level1_ids], ...]
            同一层的步骤可并行执行

        Raises:
            CyclicDependencyError: 存在循环依赖
        """
        ...

    def get_ready_steps(
        self,
        steps: list[Step],
        completed: set[str],
    ) -> list[Step]:
        """
        获取可执行的步骤

        Args:
            steps: 所有步骤
            completed: 已完成的步骤 ID 集合

        Returns:
            依赖已满足、可以执行的步骤列表
        """
        ...

    def validate_dag(self, steps: list[Step]) -> bool:
        """
        验证 DAG 有效性

        检查:
        - 无循环依赖
        - 所有依赖存在
        - 至少有一个入口节点

        Args:
            steps: 步骤列表

        Returns:
            是否有效
        """
        ...


@runtime_checkable
class IStepExecutor(Protocol):
    """
    步骤执行器接口

    负责单个 Step 的执行。
    """

    async def execute(
        self,
        step: Step,
        upstream_results: dict[str, Any],
    ) -> StepResult:
        """
        执行单个步骤

        Args:
            step: 要执行的步骤
            upstream_results: 上游步骤的结果 (按 step_id 索引)

        Returns:
            步骤执行结果

        执行流程:
        1. 获取资源租约 (如需要)
        2. 构建 AgentCall
        3. 路由到合适的 Agent
        4. 调用 Agent.invoke()
        5. Critic 验证结果
        6. 释放租约
        7. 返回结果
        """
        ...


@runtime_checkable
class IOrchestrator(Protocol):
    """
    编排器接口

    负责整个 Task 的执行编排。
    """

    async def execute_task(self, task_id: str) -> None:
        """
        执行任务

        Args:
            task_id: 任务 ID

        执行流程:
        1. 加载 Task
        2. NegotiatorAgent 协商意图 (可选)
        3. PlannerAgent 生成 Steps
        4. DAGScheduler 调度执行
        5. 逐层执行 Steps
        6. 汇总结果
        7. 更新 Task 状态
        """
        ...

    async def pause_task(self, task_id: str) -> None:
        """暂停任务"""
        ...

    async def resume_task(self, task_id: str) -> None:
        """恢复任务"""
        ...

    async def cancel_task(self, task_id: str) -> None:
        """取消任务"""
        ...
