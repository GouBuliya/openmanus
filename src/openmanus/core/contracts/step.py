"""
@PURPOSE: 定义 DAG 中的执行步骤契约
@OUTLINE:
    - enum StepStatus: 步骤状态枚举 (pending/running/succeeded/failed等)
    - class StepResult: 步骤执行结果
    - class Step: 步骤定义，包含依赖、能力、AgentCall模板
@GOTCHAS:
    - Step 的 deps 字段定义 DAG 依赖关系
    - 使用 is_ready() 检查依赖是否满足
    - build_agent_call() 构建运行时 AgentCall
@DEPENDENCIES:
    - 内部: openmanus.core.contracts.agent_call
    - 外部: pydantic, datetime, enum
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from openmanus.core.contracts.agent_call import AgentCall


class StepStatus(StrEnum):
    """Step 状态 - 生命周期状态机"""

    PENDING = "pending"  # 等待调度
    WAITING_DEPS = "waiting_deps"  # 等待依赖完成
    LEASED = "leased"  # 已获取资源租约
    RUNNING = "running"  # 执行中
    SUCCEEDED = "succeeded"  # 成功完成
    FAILED_RETRYABLE = "failed_retryable"  # 失败可重试
    FAILED_RESOURCE = "failed_resource"  # 资源失败，需切换
    FAILED_FATAL = "failed_fatal"  # 致命失败
    NEEDS_USER = "needs_user"  # 需要用户介入
    CANCELLED = "cancelled"  # 已取消
    LEASE_TIMEOUT = "lease_timeout"  # 租约超时


class StepResult(BaseModel):
    """Step 执行结果"""

    step_id: str
    status: StepStatus
    outputs: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    retry_count: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0

    model_config = {"frozen": True}


class Step(BaseModel):
    """
    Step - DAG 调度的基本执行单元

    每个 Step 代表一个需要执行的子任务，由 PlannerAgent 生成。
    Step 之间可以有依赖关系，形成 DAG。

    Example:
        >>> step = Step(
        ...     id="step_001",
        ...     name="搜索商品",
        ...     description="在淘宝搜索 iPhone 15",
        ...     capability="browser.search",
        ...     deps=[],  # 无依赖
        ...     agent_call_template={
        ...         "intent": "在淘宝搜索 iPhone 15",
        ...         "return_spec": {"schema_id": "search_result"},
        ...         "success_criteria": {"conditions": ["返回搜索结果"]},
        ...     },
        ... )
    """

    # =========================================================================
    # 标识
    # =========================================================================
    id: str = Field(..., description="步骤 ID，格式: step_{uuid}")
    name: str = Field(..., min_length=1, max_length=200, description="步骤名称")
    description: str = Field(default="", max_length=2000, description="步骤描述")

    # =========================================================================
    # 依赖关系
    # =========================================================================
    deps: list[str] = Field(
        default_factory=list,
        description="依赖的步骤 ID 列表",
    )

    # =========================================================================
    # Agent 配置
    # =========================================================================
    capability: str = Field(
        ...,
        description="所需 Agent 能力，格式: {domain}.{action}",
    )
    agent_call_template: dict[str, Any] = Field(
        ...,
        description="AgentCall 模板 (不含 tracing，运行时填充)",
    )

    # =========================================================================
    # 状态
    # =========================================================================
    status: StepStatus = Field(default=StepStatus.PENDING)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0, le=10)

    # =========================================================================
    # 资源
    # =========================================================================
    lease_id: str | None = Field(default=None, description="当前持有的租约 ID")
    preferred_resource_labels: dict[str, str] = Field(
        default_factory=dict,
        description="首选资源标签",
    )

    # =========================================================================
    # 结果
    # =========================================================================
    result: StepResult | None = Field(default=None)

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

    def is_ready(self, completed_steps: set[str]) -> bool:
        """检查是否可以执行 (所有依赖已完成)"""
        return all(dep in completed_steps for dep in self.deps)

    def is_terminal(self) -> bool:
        """检查是否处于终态"""
        return self.status in {
            StepStatus.SUCCEEDED,
            StepStatus.FAILED_FATAL,
            StepStatus.CANCELLED,
        }

    def is_failed(self) -> bool:
        """检查是否失败"""
        return self.status in {
            StepStatus.FAILED_RETRYABLE,
            StepStatus.FAILED_RESOURCE,
            StepStatus.FAILED_FATAL,
        }

    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return (
            self.status == StepStatus.FAILED_RETRYABLE and self.retry_count < self.max_retries
        )

    def build_agent_call(
        self,
        task_id: str,
        call_id: str,
        upstream_results: dict[str, Any] | None = None,
    ) -> AgentCall:
        """
        构建完整的 AgentCall

        Args:
            task_id: 任务 ID
            call_id: 调用 ID
            upstream_results: 上游步骤结果 (按步骤 ID 索引)

        Returns:
            完整的 AgentCall 对象
        """
        from openmanus.core.contracts.agent_call import TracingContext

        # 合并模板和运行时数据
        call_data = {
            **self.agent_call_template,
            "upstream_results": upstream_results or {},
            "tracing": TracingContext(
                task_id=task_id,
                step_id=self.id,
                call_id=call_id,
            ),
        }

        return AgentCall.model_validate(call_data)

    def with_status(self, status: StepStatus) -> "Step":
        """更新状态，返回新的 Step"""
        updates: dict[str, Any] = {"status": status}
        if status == StepStatus.RUNNING and self.started_at is None:
            updates["started_at"] = datetime.utcnow()
        if status in {StepStatus.SUCCEEDED, StepStatus.FAILED_FATAL, StepStatus.CANCELLED}:
            updates["completed_at"] = datetime.utcnow()
        return self.model_copy(update=updates)

    def with_result(self, result: StepResult) -> "Step":
        """设置结果，返回新的 Step"""
        return self.model_copy(
            update={
                "result": result,
                "status": result.status,
                "completed_at": datetime.utcnow(),
            }
        )

    def increment_retry(self) -> "Step":
        """增加重试次数，返回新的 Step"""
        return self.model_copy(update={"retry_count": self.retry_count + 1})
