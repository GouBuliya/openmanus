"""
OpenManus 契约模块

定义平台所有核心数据契约，使用 Pydantic v2 进行验证。
所有 Agent 调用和返回都必须符合这些契约。
"""

from openmanus.core.contracts.agent_call import (
    AgentCall,
    Constraints,
    ExecutionConfig,
    ModelProfile,
    ReturnSpec,
    RetryPolicy,
    SuccessCriteria,
    TracingContext,
    VerificationConfig,
)
from openmanus.core.contracts.agent_result import (
    AgentResult,
    EvidenceItem,
    ExecutionMetrics,
    ResultStatus,
)
from openmanus.core.contracts.evidence import (
    Evidence,
    EvidenceType,
)
from openmanus.core.contracts.lease import (
    Lease,
    LeaseRequest,
    LeaseStatus,
    Resource,
    ResourceHealth,
    ResourceType,
)
from openmanus.core.contracts.step import (
    Step,
    StepStatus,
)
from openmanus.core.contracts.task import (
    Task,
    TaskPriority,
    TaskStatus,
)

__all__ = [
    # agent_call
    "AgentCall",
    "ReturnSpec",
    "SuccessCriteria",
    "Constraints",
    "ExecutionConfig",
    "ModelProfile",
    "RetryPolicy",
    "VerificationConfig",
    "TracingContext",
    # agent_result
    "AgentResult",
    "ResultStatus",
    "EvidenceItem",
    "ExecutionMetrics",
    # evidence
    "Evidence",
    "EvidenceType",
    # lease
    "Lease",
    "LeaseRequest",
    "LeaseStatus",
    "Resource",
    "ResourceType",
    "ResourceHealth",
    # step
    "Step",
    "StepStatus",
    # task
    "Task",
    "TaskStatus",
    "TaskPriority",
]
