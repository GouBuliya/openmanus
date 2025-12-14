"""
@PURPOSE: 实现模型选择策略引擎
@OUTLINE:
    - class PolicyEngine: 策略引擎
        - 根据任务类型选择模型
        - 考虑成本和性能平衡
        - 支持自定义策略
@GOTCHAS:
    - 策略可以组合使用
    - 降级策略用于主模型不可用时
@DEPENDENCIES:
    - 内部: openmanus.llm.model_registry
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class TaskComplexity(str, Enum):
    """任务复杂度"""

    LOW = "low"  # 简单任务
    MEDIUM = "medium"  # 中等任务
    HIGH = "high"  # 复杂任务
    CRITICAL = "critical"  # 关键任务


@dataclass
class ModelSelection:
    """模型选择结果"""

    model: str
    reason: str
    fallback: str | None = None


class IModelSelectionPolicy(Protocol):
    """模型选择策略协议"""

    def select(
        self,
        task_type: str,
        complexity: TaskComplexity,
        context: dict,
    ) -> ModelSelection:
        """
        选择模型

        Args:
            task_type: 任务类型
            complexity: 任务复杂度
            context: 上下文信息

        Returns:
            模型选择结果
        """
        ...


class CostOptimizedPolicy:
    """成本优化策略"""

    MODEL_BY_COMPLEXITY = {
        TaskComplexity.LOW: "deepseek-chat",
        TaskComplexity.MEDIUM: "gpt-3.5-turbo",
        TaskComplexity.HIGH: "gpt-4-turbo",
        TaskComplexity.CRITICAL: "claude-3-opus",
    }

    def select(
        self,
        task_type: str,
        complexity: TaskComplexity,
        context: dict,
    ) -> ModelSelection:
        """根据复杂度选择成本最优模型"""
        model = self.MODEL_BY_COMPLEXITY.get(complexity, "gpt-3.5-turbo")

        return ModelSelection(
            model=model,
            reason=f"成本优化: 复杂度 {complexity.value}",
            fallback="gpt-3.5-turbo",
        )


class QualityOptimizedPolicy:
    """质量优化策略"""

    def select(
        self,
        task_type: str,
        complexity: TaskComplexity,
        context: dict,
    ) -> ModelSelection:
        """始终选择最高质量模型"""
        return ModelSelection(
            model="claude-3-opus",
            reason="质量优化: 使用最强模型",
            fallback="gpt-4",
        )


class PolicyEngine:
    """
    模型选择策略引擎

    根据任务特征选择最合适的模型。

    Example:
        >>> engine = PolicyEngine()
        >>> selection = engine.select_model(
        ...     task_type="planning",
        ...     complexity=TaskComplexity.HIGH,
        ... )
        >>> print(selection.model)
    """

    # 任务类型到复杂度的默认映射
    TASK_COMPLEXITY_MAP = {
        "planning": TaskComplexity.HIGH,
        "execution": TaskComplexity.MEDIUM,
        "verification": TaskComplexity.MEDIUM,
        "extraction": TaskComplexity.LOW,
        "summarization": TaskComplexity.LOW,
    }

    def __init__(
        self,
        default_policy: IModelSelectionPolicy | None = None,
    ) -> None:
        """
        初始化策略引擎

        Args:
            default_policy: 默认策略
        """
        self._default_policy = default_policy or CostOptimizedPolicy()
        self._task_policies: dict[str, IModelSelectionPolicy] = {}

    def register_policy(
        self,
        task_type: str,
        policy: IModelSelectionPolicy,
    ) -> None:
        """
        为特定任务类型注册策略

        Args:
            task_type: 任务类型
            policy: 选择策略
        """
        self._task_policies[task_type] = policy

    def select_model(
        self,
        task_type: str,
        complexity: TaskComplexity | None = None,
        context: dict | None = None,
    ) -> ModelSelection:
        """
        选择模型

        Args:
            task_type: 任务类型
            complexity: 任务复杂度 (可选，会自动推断)
            context: 上下文信息

        Returns:
            模型选择结果
        """
        # 推断复杂度
        if complexity is None:
            complexity = self.TASK_COMPLEXITY_MAP.get(
                task_type, TaskComplexity.MEDIUM
            )

        # 获取策略
        policy = self._task_policies.get(task_type, self._default_policy)

        # 执行选择
        return policy.select(task_type, complexity, context or {})

    def set_default_policy(self, policy: IModelSelectionPolicy) -> None:
        """设置默认策略"""
        self._default_policy = policy

    def __repr__(self) -> str:
        return (
            f"<PolicyEngine policies={list(self._task_policies.keys())}>"
        )
