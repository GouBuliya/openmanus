"""
@PURPOSE: 定义用户任务的顶层契约
@OUTLINE:
    - enum TaskStatus: 任务状态枚举
    - enum TaskPriority: 任务优先级
    - class TaskResult: 任务最终结果
    - class Task: 顶层任务定义，包含用户输入、Steps、状态、结果
@GOTCHAS:
    - Task 的 steps 字段形成 DAG
    - 使用 get_ready_steps() 获取可执行步骤
    - compute_result() 汇总所有步骤结果
@DEPENDENCIES:
    - 内部: openmanus.core.contracts.step
    - 外部: pydantic, datetime, enum
"""

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field

from openmanus.core.contracts.step import Step, StepStatus


class TaskStatus(StrEnum):
    """Task 状态"""

    CREATED = "created"  # 刚创建
    NEGOTIATING = "negotiating"  # 意图协商中
    PLANNING = "planning"  # 规划中
    SCHEDULED = "scheduled"  # 已调度
    RUNNING = "running"  # 执行中
    PAUSED = "paused"  # 已暂停
    SUCCEEDED = "succeeded"  # 成功完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消
    NEEDS_USER = "needs_user"  # 需要用户介入


class TaskPriority(IntEnum):
    """Task 优先级"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class TaskResult(BaseModel):
    """Task 最终结果"""

    success: bool
    outputs: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(default="")
    error_message: str | None = None

    # 聚合指标
    total_steps: int = 0
    succeeded_steps: int = 0
    failed_steps: int = 0
    total_duration_ms: int = 0
    total_cost_usd: float = 0.0

    # 证据汇总
    evidence_uris: list[str] = Field(default_factory=list)
    replay_uri: str | None = None

    model_config = {"frozen": True}


class Task(BaseModel):
    """
    Task - 用户提交的顶层任务

    Task 是整个执行流程的入口，由用户通过 API 提交。
    经过 NegotiatorAgent (可选) 和 PlannerAgent 处理后，
    生成 Steps 并由 DAGScheduler 调度执行。

    Example:
        >>> task = Task(
        ...     id="task_abc123",
        ...     user_input="帮我在淘宝搜索 iPhone 15，对比前5个商品的价格",
        ...     tenant_id="tenant_001",
        ... )
    """

    # =========================================================================
    # 标识
    # =========================================================================
    id: str = Field(..., description="任务 ID，格式: task_{uuid}")
    tenant_id: str = Field(..., description="租户 ID")
    user_id: str | None = Field(default=None, description="用户 ID")

    # =========================================================================
    # 用户输入
    # =========================================================================
    user_input: str = Field(..., min_length=1, max_length=50000, description="原始用户输入")
    user_context: str | None = Field(default=None, description="用户上下文")

    # =========================================================================
    # 状态
    # =========================================================================
    status: TaskStatus = Field(default=TaskStatus.CREATED)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)

    # =========================================================================
    # 意图协商结果 (可选)
    # =========================================================================
    negotiated_intent: str | None = Field(default=None, description="协商后的明确意图")
    negotiation_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # =========================================================================
    # 执行计划
    # =========================================================================
    steps: list[Step] = Field(default_factory=list, description="执行步骤 (DAG)")

    # =========================================================================
    # 结果
    # =========================================================================
    result: TaskResult | None = Field(default=None)

    # =========================================================================
    # 约束
    # =========================================================================
    timeout_ms: int = Field(default=600000, ge=10000, le=3600000, description="总超时时间")
    cost_budget_usd: float = Field(default=1.0, ge=0.0, le=100.0, description="成本预算")

    # =========================================================================
    # 时间戳
    # =========================================================================
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # =========================================================================
    # 元数据
    # =========================================================================
    metadata: dict[str, str] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict, description="K8s 风格标签")

    # =========================================================================
    # 链路追踪
    # =========================================================================
    trace_id: str | None = Field(default=None, description="OpenTelemetry trace_id")

    def is_terminal(self) -> bool:
        """检查是否处于终态"""
        return self.status in {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }

    def get_ready_steps(self) -> list[Step]:
        """获取可以执行的步骤 (依赖已满足)"""
        completed_ids = {s.id for s in self.steps if s.status == StepStatus.SUCCEEDED}
        return [
            s
            for s in self.steps
            if s.status == StepStatus.PENDING and s.is_ready(completed_ids)
        ]

    def get_step_by_id(self, step_id: str) -> Step | None:
        """根据 ID 获取步骤"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def compute_progress(self) -> float:
        """计算执行进度 (0.0 - 1.0)"""
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.is_terminal())
        return completed / len(self.steps)

    def compute_result(self) -> TaskResult:
        """根据步骤结果计算最终结果"""
        total = len(self.steps)
        succeeded = sum(1 for s in self.steps if s.status == StepStatus.SUCCEEDED)
        failed = sum(1 for s in self.steps if s.is_failed())

        # 聚合输出
        outputs: dict[str, Any] = {}
        evidence_uris: list[str] = []
        total_duration = 0
        total_cost = 0.0

        for step in self.steps:
            if step.result:
                outputs[step.id] = step.result.outputs
                total_duration += step.result.duration_ms
                total_cost += step.result.cost_usd

        success = failed == 0 and succeeded == total

        return TaskResult(
            success=success,
            outputs=outputs,
            summary=f"完成 {succeeded}/{total} 步骤" + ("" if success else f"，失败 {failed} 步骤"),
            total_steps=total,
            succeeded_steps=succeeded,
            failed_steps=failed,
            total_duration_ms=total_duration,
            total_cost_usd=total_cost,
            evidence_uris=evidence_uris,
        )

    def with_status(self, status: TaskStatus) -> "Task":
        """更新状态，返回新的 Task"""
        updates: dict[str, Any] = {"status": status}
        if status == TaskStatus.RUNNING and self.started_at is None:
            updates["started_at"] = datetime.utcnow()
        if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            updates["completed_at"] = datetime.utcnow()
        return self.model_copy(update=updates)

    def with_steps(self, steps: list[Step]) -> "Task":
        """设置步骤，返回新的 Task"""
        return self.model_copy(update={"steps": steps, "status": TaskStatus.SCHEDULED})

    def with_result(self, result: TaskResult) -> "Task":
        """设置结果，返回新的 Task"""
        status = TaskStatus.SUCCEEDED if result.success else TaskStatus.FAILED
        return self.model_copy(
            update={
                "result": result,
                "status": status,
                "completed_at": datetime.utcnow(),
            }
        )
