"""
@PURPOSE: 定义资源租约契约，实现资源访问控制
@OUTLINE:
    - enum ResourceType: 资源类型 (browser/mobile/container/vm)
    - enum ResourceHealth: 资源健康状态
    - enum LeaseStatus: 租约状态
    - class ResourceEndpoint: 资源端点
    - class Resource: 可租用资源定义
    - class LeaseRequest: 租约请求
    - class Lease: 租约定义
@GOTCHAS:
    - 执行类 Agent 必须持有有效租约才能操作资源
    - 租约有时效限制，使用 renew() 续约
    - 使用 is_valid() 检查租约有效性
@DEPENDENCIES:
    - 外部: pydantic, datetime, enum
"""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResourceType(StrEnum):
    """资源类型"""

    BROWSER = "browser"  # 浏览器实例
    MOBILE = "mobile"  # 移动设备
    CONTAINER = "container"  # 容器
    VM = "vm"  # 虚拟机


class ResourceHealth(StrEnum):
    """资源健康状态"""

    OK = "ok"  # 健康
    DEGRADED = "degraded"  # 降级
    DOWN = "down"  # 不可用
    UNKNOWN = "unknown"  # 未知


class LeaseStatus(StrEnum):
    """租约状态"""

    ACTIVE = "active"  # 活跃
    EXPIRED = "expired"  # 已过期
    RELEASED = "released"  # 已释放
    REVOKED = "revoked"  # 已撤销


class ResourceEndpoint(BaseModel):
    """资源端点"""

    type: str = Field(..., description="端点类型: cdp, webdriver, ssh, grpc, etc.")
    url: str = Field(..., description="端点 URL")
    auth: dict[str, str] = Field(default_factory=dict, description="认证信息")

    model_config = {"frozen": True}


class Resource(BaseModel):
    """
    Resource - 可租用的执行资源

    资源是执行 Agent 进行外部操作的载体。
    包括浏览器实例、移动设备、容器、虚拟机等。

    Example:
        >>> resource = Resource(
        ...     id="browser_abc123",
        ...     type=ResourceType.BROWSER,
        ...     capabilities=["browser.navigate", "browser.screenshot"],
        ...     labels={"region": "us-west-1", "browser": "chrome"},
        ...     endpoints=[
        ...         ResourceEndpoint(type="cdp", url="ws://localhost:9222"),
        ...     ],
        ... )
    """

    # =========================================================================
    # 标识
    # =========================================================================
    id: str = Field(..., description="资源 ID，格式: {type}_{uuid}")
    name: str = Field(default="", description="资源名称")
    type: ResourceType = Field(..., description="资源类型")

    # =========================================================================
    # 能力
    # =========================================================================
    capabilities: list[str] = Field(
        default_factory=list,
        description="支持的能力列表，格式: {domain}.{action}",
    )

    # =========================================================================
    # 标签 (K8s 风格)
    # =========================================================================
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="资源标签: region, os, browser, tenant, etc.",
    )

    # =========================================================================
    # 端点
    # =========================================================================
    endpoints: list[ResourceEndpoint] = Field(
        default_factory=list,
        description="资源端点列表",
    )

    # =========================================================================
    # 状态
    # =========================================================================
    health: ResourceHealth = Field(default=ResourceHealth.UNKNOWN)
    is_leased: bool = Field(default=False, description="是否已被租用")
    current_lease_id: str | None = Field(default=None)

    # =========================================================================
    # 限制
    # =========================================================================
    max_concurrent: int = Field(default=1, ge=1, description="最大并发数")
    cpu_limit: float = Field(default=1.0, ge=0.1, description="CPU 限制 (核)")
    memory_limit_mb: int = Field(default=1024, ge=128, description="内存限制 (MB)")

    # =========================================================================
    # 时间戳
    # =========================================================================
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_health_check: datetime | None = None

    # =========================================================================
    # 元数据
    # =========================================================================
    metadata: dict[str, Any] = Field(default_factory=dict)

    def matches_capabilities(self, required: list[str]) -> bool:
        """检查是否满足所需能力"""
        return all(cap in self.capabilities for cap in required)

    def matches_labels(self, required: dict[str, str]) -> bool:
        """检查是否满足所需标签"""
        return all(self.labels.get(k) == v for k, v in required.items())

    def is_available(self) -> bool:
        """检查是否可用"""
        return (
            not self.is_leased
            and self.health in {ResourceHealth.OK, ResourceHealth.DEGRADED}
        )

    def get_endpoint(self, endpoint_type: str) -> ResourceEndpoint | None:
        """获取指定类型的端点"""
        for ep in self.endpoints:
            if ep.type == endpoint_type:
                return ep
        return None


class LeaseRequest(BaseModel):
    """租约请求"""

    # =========================================================================
    # 请求者
    # =========================================================================
    task_id: str = Field(..., description="任务 ID")
    step_id: str = Field(..., description="步骤 ID")

    # =========================================================================
    # 资源要求
    # =========================================================================
    resource_type: ResourceType = Field(..., description="资源类型")
    capabilities: list[str] = Field(
        default_factory=list,
        description="所需能力",
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="首选标签",
    )

    # =========================================================================
    # 租约配置
    # =========================================================================
    duration_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="租约时长 (秒)",
    )
    auto_renew: bool = Field(default=True, description="是否自动续约")
    max_renew_count: int = Field(default=3, ge=0, le=10, description="最大续约次数")

    # =========================================================================
    # 优先级
    # =========================================================================
    priority: int = Field(default=0, ge=0, le=100, description="请求优先级")

    model_config = {"frozen": True}


class Lease(BaseModel):
    """
    Lease - 资源租约

    Lease 是资源访问控制的凭证。
    执行类 Agent 必须持有有效租约才能操作对应资源。

    Example:
        >>> lease = Lease(
        ...     id="lease_xyz789",
        ...     resource_id="browser_abc123",
        ...     task_id="task_001",
        ...     step_id="step_001",
        ...     expires_at=datetime.utcnow() + timedelta(minutes=5),
        ... )
    """

    # =========================================================================
    # 标识
    # =========================================================================
    id: str = Field(..., description="租约 ID，格式: lease_{uuid}")

    # =========================================================================
    # 关联
    # =========================================================================
    resource_id: str = Field(..., description="资源 ID")
    task_id: str = Field(..., description="任务 ID")
    step_id: str = Field(..., description="步骤 ID")

    # =========================================================================
    # 状态
    # =========================================================================
    status: LeaseStatus = Field(default=LeaseStatus.ACTIVE)

    # =========================================================================
    # 时间
    # =========================================================================
    acquired_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="过期时间")
    last_renewed_at: datetime | None = None
    released_at: datetime | None = None

    # =========================================================================
    # 续约
    # =========================================================================
    renew_count: int = Field(default=0, ge=0)
    max_renew_count: int = Field(default=3, ge=0)
    auto_renew: bool = Field(default=True)

    # =========================================================================
    # 元数据
    # =========================================================================
    metadata: dict[str, str] = Field(default_factory=dict)

    def is_valid(self) -> bool:
        """检查租约是否有效"""
        return self.status == LeaseStatus.ACTIVE and datetime.utcnow() < self.expires_at

    def is_expired(self) -> bool:
        """检查是否已过期"""
        return datetime.utcnow() >= self.expires_at

    def can_renew(self) -> bool:
        """检查是否可以续约"""
        return (
            self.status == LeaseStatus.ACTIVE
            and self.renew_count < self.max_renew_count
        )

    def remaining_seconds(self) -> float:
        """剩余时间 (秒)"""
        delta = self.expires_at - datetime.utcnow()
        return max(0.0, delta.total_seconds())

    def renew(self, extension_seconds: int = 300) -> "Lease":
        """续约，返回新的 Lease"""
        if not self.can_renew():
            raise ValueError("Cannot renew lease")

        new_expires = datetime.utcnow() + timedelta(seconds=extension_seconds)
        return self.model_copy(
            update={
                "expires_at": new_expires,
                "last_renewed_at": datetime.utcnow(),
                "renew_count": self.renew_count + 1,
            }
        )

    def release(self) -> "Lease":
        """释放租约，返回新的 Lease"""
        return self.model_copy(
            update={
                "status": LeaseStatus.RELEASED,
                "released_at": datetime.utcnow(),
            }
        )

    def expire(self) -> "Lease":
        """标记过期，返回新的 Lease"""
        return self.model_copy(update={"status": LeaseStatus.EXPIRED})

    def revoke(self) -> "Lease":
        """撤销租约，返回新的 Lease"""
        return self.model_copy(
            update={
                "status": LeaseStatus.REVOKED,
                "released_at": datetime.utcnow(),
            }
        )
