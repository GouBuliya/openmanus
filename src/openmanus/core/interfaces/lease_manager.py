"""
@PURPOSE: 定义资源租约管理器接口协议
@OUTLINE:
    - protocol ILeaseManager: 租约管理接口 (acquire, renew, release, validate)
    - protocol IResourcePool: 资源池接口
@DEPENDENCIES:
    - 内部: openmanus.core.contracts.lease
    - 外部: typing.Protocol
"""

from typing import Protocol, runtime_checkable

from openmanus.core.contracts.lease import Lease, LeaseRequest, Resource


@runtime_checkable
class ILeaseManager(Protocol):
    """
    租约管理器接口

    负责:
    - 资源租约的获取、续约、释放
    - 资源可用性检查
    - 租约过期处理
    - 资源清理
    """

    async def acquire(self, request: LeaseRequest) -> Lease:
        """
        获取资源租约

        Args:
            request: 租约请求，包含资源类型、能力要求等

        Returns:
            有效的租约

        Raises:
            LeaseAcquireError: 无法获取租约
            ResourceNotAvailableError: 无可用资源

        流程:
        1. 根据要求查找可用资源
        2. 原子性地标记资源为已租用
        3. 创建租约记录
        4. 返回租约
        """
        ...

    async def renew(self, lease_id: str, extension_seconds: int = 300) -> Lease:
        """
        续约

        Args:
            lease_id: 租约 ID
            extension_seconds: 延长秒数

        Returns:
            续约后的租约

        Raises:
            LeaseNotFoundError: 租约不存在
            LeaseExpiredError: 租约已过期
        """
        ...

    async def release(self, lease_id: str) -> None:
        """
        释放租约

        Args:
            lease_id: 租约 ID

        流程:
        1. 标记租约为已释放
        2. 标记资源为可用
        3. 触发资源清理 (如需要)
        """
        ...

    async def get(self, lease_id: str) -> Lease | None:
        """
        获取租约信息

        Args:
            lease_id: 租约 ID

        Returns:
            租约，不存在返回 None
        """
        ...

    async def validate(self, lease_id: str) -> bool:
        """
        验证租约有效性

        Args:
            lease_id: 租约 ID

        Returns:
            租约是否有效
        """
        ...

    async def cleanup_expired(self) -> int:
        """
        清理过期租约

        Returns:
            清理的租约数量

        流程:
        1. 查找所有过期租约
        2. 标记租约为过期
        3. 释放对应资源
        4. 触发资源清理
        """
        ...


@runtime_checkable
class IResourcePool(Protocol):
    """
    资源池接口

    管理可用资源的池化。
    """

    async def register(self, resource: Resource) -> None:
        """注册资源"""
        ...

    async def unregister(self, resource_id: str) -> None:
        """注销资源"""
        ...

    async def get(self, resource_id: str) -> Resource | None:
        """获取资源"""
        ...

    async def find_available(
        self,
        resource_type: str,
        capabilities: list[str] | None = None,
        labels: dict[str, str] | None = None,
    ) -> Resource | None:
        """
        查找可用资源

        Args:
            resource_type: 资源类型
            capabilities: 所需能力
            labels: 首选标签

        Returns:
            可用资源，无则返回 None
        """
        ...

    async def mark_leased(self, resource_id: str, lease_id: str) -> None:
        """标记资源为已租用"""
        ...

    async def mark_available(self, resource_id: str) -> None:
        """标记资源为可用"""
        ...

    async def update_health(self, resource_id: str, health: str) -> None:
        """更新资源健康状态"""
        ...

    async def list_all(self) -> list[Resource]:
        """列出所有资源"""
        ...

    async def list_available(self) -> list[Resource]:
        """列出所有可用资源"""
        ...
