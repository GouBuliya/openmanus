"""
@PURPOSE: 定义平台所有自定义异常类，按模块分层组织
@OUTLINE:
    - class OpenManusError: 基础异常类
    - 契约异常: ContractError, ValidationError, SchemaError
    - Agent异常: AgentError, AgentNotFoundError, AgentTimeoutError, AgentExecutionError
    - 资源异常: ResourceError, LeaseError, LeaseNotFoundError, LeaseExpiredError
    - 编排异常: OrchestrationError, DAGError, CyclicDependencyError, StepError
    - LLM异常: LLMError, LLMRateLimitError, LLMQuotaExceededError
    - 验证异常: VerificationError, VerificationFailedError, ConsensusError
    - 安全异常: SecurityError, PermissionDeniedError, RiskLevelExceededError
@DEPENDENCIES:
    - 外部: typing
"""

from typing import Any


class OpenManusError(Exception):
    """OpenManus 平台基础异常类"""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message


# =============================================================================
# 契约相关异常
# =============================================================================


class ContractError(OpenManusError):
    """契约违规异常"""

    pass


class ValidationError(ContractError):
    """契约验证失败"""

    pass


class SchemaError(ContractError):
    """Schema 不匹配"""

    pass


# =============================================================================
# Agent 相关异常
# =============================================================================


class AgentError(OpenManusError):
    """Agent 执行异常"""

    pass


class AgentNotFoundError(AgentError):
    """Agent 未找到"""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent not found: {agent_id}", {"agent_id": agent_id})


class AgentTimeoutError(AgentError):
    """Agent 执行超时"""

    def __init__(self, agent_id: str, timeout_ms: int) -> None:
        super().__init__(
            f"Agent timeout after {timeout_ms}ms: {agent_id}",
            {"agent_id": agent_id, "timeout_ms": timeout_ms},
        )


class AgentExecutionError(AgentError):
    """Agent 执行失败"""

    pass


# =============================================================================
# 资源相关异常
# =============================================================================


class ResourceError(OpenManusError):
    """资源管理异常"""

    pass


class LeaseError(ResourceError):
    """租约异常"""

    pass


class LeaseNotFoundError(LeaseError):
    """租约未找到"""

    def __init__(self, lease_id: str) -> None:
        super().__init__(f"Lease not found: {lease_id}", {"lease_id": lease_id})


class LeaseExpiredError(LeaseError):
    """租约已过期"""

    def __init__(self, lease_id: str) -> None:
        super().__init__(f"Lease expired: {lease_id}", {"lease_id": lease_id})


class LeaseAcquireError(LeaseError):
    """无法获取租约"""

    pass


class ResourceNotAvailableError(ResourceError):
    """资源不可用"""

    def __init__(self, resource_type: str, capabilities: list[str] | None = None) -> None:
        super().__init__(
            f"No available resource of type: {resource_type}",
            {"resource_type": resource_type, "capabilities": capabilities or []},
        )


class ResourceHealthError(ResourceError):
    """资源健康检查失败"""

    pass


# =============================================================================
# 编排相关异常
# =============================================================================


class OrchestrationError(OpenManusError):
    """编排异常"""

    pass


class DAGError(OrchestrationError):
    """DAG 调度异常"""

    pass


class CyclicDependencyError(DAGError):
    """DAG 存在循环依赖"""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__(f"Cyclic dependency detected: {' -> '.join(cycle)}", {"cycle": cycle})


class StepError(OrchestrationError):
    """Step 执行异常"""

    pass


class StepNotFoundError(StepError):
    """Step 未找到"""

    def __init__(self, step_id: str) -> None:
        super().__init__(f"Step not found: {step_id}", {"step_id": step_id})


class StepTimeoutError(StepError):
    """Step 执行超时"""

    pass


class StepRetryExhaustedError(StepError):
    """Step 重试次数耗尽"""

    def __init__(self, step_id: str, max_retries: int) -> None:
        super().__init__(
            f"Step retry exhausted after {max_retries} attempts: {step_id}",
            {"step_id": step_id, "max_retries": max_retries},
        )


# =============================================================================
# LLM 相关异常
# =============================================================================


class LLMError(OpenManusError):
    """LLM 调用异常"""

    pass


class LLMRateLimitError(LLMError):
    """LLM 速率限制"""

    pass


class LLMQuotaExceededError(LLMError):
    """LLM 配额超限"""

    def __init__(self, budget_usd: float, used_usd: float) -> None:
        super().__init__(
            f"LLM quota exceeded: used ${used_usd:.4f} of ${budget_usd:.4f}",
            {"budget_usd": budget_usd, "used_usd": used_usd},
        )


class LLMProviderError(LLMError):
    """LLM 供应商错误"""

    pass


# =============================================================================
# 验证相关异常
# =============================================================================


class VerificationError(OpenManusError):
    """验证异常"""

    pass


class VerificationFailedError(VerificationError):
    """验证失败"""

    pass


class ConsensusError(VerificationError):
    """共识未达成"""

    pass


# =============================================================================
# 安全相关异常
# =============================================================================


class SecurityError(OpenManusError):
    """安全异常"""

    pass


class PermissionDeniedError(SecurityError):
    """权限不足"""

    pass


class SecretAccessError(SecurityError):
    """Secret 访问异常"""

    pass


class RiskLevelExceededError(SecurityError):
    """风险等级超限"""

    def __init__(self, required_level: str, current_level: str) -> None:
        super().__init__(
            f"Risk level exceeded: required={required_level}, current={current_level}",
            {"required_level": required_level, "current_level": current_level},
        )
