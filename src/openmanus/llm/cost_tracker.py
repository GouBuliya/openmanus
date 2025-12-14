"""
@PURPOSE: 实现成本追踪器，监控 LLM 使用成本
@OUTLINE:
    - class CostTracker: 成本追踪器
        - 记录每次调用成本
        - 按任务/模型汇总
        - 预算告警
@DEPENDENCIES:
    - 外部: datetime
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CostRecord:
    """成本记录"""

    model: str
    task_id: str
    step_id: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CostSummary:
    """成本汇总"""

    total_cost_usd: float = 0.0
    total_tokens: int = 0
    call_count: int = 0
    by_model: dict[str, float] = field(default_factory=dict)
    by_task: dict[str, float] = field(default_factory=dict)


class CostTracker:
    """
    成本追踪器

    追踪和汇总 LLM 使用成本。

    Example:
        >>> tracker = CostTracker(budget_usd=10.0)
        >>> tracker.record(
        ...     model="gpt-4",
        ...     task_id="task_001",
        ...     prompt_tokens=100,
        ...     completion_tokens=50,
        ...     cost_usd=0.01,
        ... )
        >>> summary = tracker.get_summary()
    """

    def __init__(
        self,
        budget_usd: float | None = None,
        on_budget_exceeded: Callable[[float, float], None] | None = None,
    ) -> None:
        """
        初始化追踪器

        Args:
            budget_usd: 预算上限 (USD)
            on_budget_exceeded: 超预算回调
        """
        self._budget = budget_usd
        self._on_budget_exceeded = on_budget_exceeded
        self._records: list[CostRecord] = []
        self._total_cost: float = 0.0

    def record(
        self,
        model: str,
        task_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        step_id: str | None = None,
    ) -> None:
        """
        记录成本

        Args:
            model: 模型名称
            task_id: 任务 ID
            prompt_tokens: 提示 token 数
            completion_tokens: 完成 token 数
            cost_usd: 成本 (USD)
            step_id: 步骤 ID (可选)
        """
        record = CostRecord(
            model=model,
            task_id=task_id,
            step_id=step_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )

        self._records.append(record)
        self._total_cost += cost_usd

        # 检查预算
        if self._budget and self._total_cost > self._budget:
            if self._on_budget_exceeded:
                self._on_budget_exceeded(self._total_cost, self._budget)

    def get_summary(self) -> CostSummary:
        """
        获取成本汇总

        Returns:
            成本汇总
        """
        summary = CostSummary()
        summary.call_count = len(self._records)

        for record in self._records:
            summary.total_cost_usd += record.cost_usd
            summary.total_tokens += record.prompt_tokens + record.completion_tokens

            # 按模型汇总
            if record.model not in summary.by_model:
                summary.by_model[record.model] = 0.0
            summary.by_model[record.model] += record.cost_usd

            # 按任务汇总
            if record.task_id not in summary.by_task:
                summary.by_task[record.task_id] = 0.0
            summary.by_task[record.task_id] += record.cost_usd

        return summary

    def get_task_cost(self, task_id: str) -> float:
        """获取任务总成本"""
        return sum(r.cost_usd for r in self._records if r.task_id == task_id)

    def get_remaining_budget(self) -> float | None:
        """获取剩余预算"""
        if self._budget is None:
            return None
        return max(0, self._budget - self._total_cost)

    def is_budget_exceeded(self) -> bool:
        """检查是否超预算"""
        if self._budget is None:
            return False
        return self._total_cost > self._budget

    @property
    def total_cost(self) -> float:
        """总成本"""
        return self._total_cost

    @property
    def record_count(self) -> int:
        """记录数量"""
        return len(self._records)

    def clear(self) -> None:
        """清空记录"""
        self._records.clear()
        self._total_cost = 0.0

    def __repr__(self) -> str:
        return (
            f"<CostTracker total=${self._total_cost:.4f} "
            f"records={len(self._records)}>"
        )
