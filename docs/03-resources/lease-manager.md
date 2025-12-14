# 租约管理

## 概述

租约（Lease）是资源访问控制的核心机制。执行型 Agent 必须持有 Lease 才能产生外部副作用。

## 租约数据结构

```python
@dataclass
class Lease:
    """资源租约"""
    id: str
    resource_id: str
    task_id: str
    step_id: str

    acquired_at: datetime
    expires_at: datetime
    max_duration_seconds: int

    auto_renew: bool = True
    renew_threshold_seconds: int = 30
    max_renewals: int = 10
    renewal_count: int = 0

    state: LeaseState = LeaseState.ACTIVE

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def time_remaining(self) -> timedelta:
        return self.expires_at - datetime.utcnow()

    def should_renew(self) -> bool:
        return (
            self.auto_renew and
            self.renewal_count < self.max_renewals and
            self.time_remaining().total_seconds() < self.renew_threshold_seconds
        )
```

## 租约状态

```python
class LeaseState(Enum):
    ACTIVE = 'active'      # 活跃中
    RELEASED = 'released'  # 已释放
    EXPIRED = 'expired'    # 已过期
```

## 租约管理器

```python
class LeaseManager:
    """租约管理器"""

    async def acquire(self, request: LeaseRequest) -> Lease:
        """获取租约"""
        # 1. 查找可用资源
        resource = await self.resource_registry.find_available(
            capabilities=request.capabilities,
            labels=request.label_selector,
        )

        if not resource:
            raise ResourceUnavailableError("No available resource")

        # 2. 创建租约
        lease = Lease(
            id=generate_lease_id(),
            resource_id=resource.id,
            task_id=request.task_id,
            step_id=request.step_id,
            acquired_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=request.duration_seconds),
            max_duration_seconds=request.max_duration_seconds,
            auto_renew=request.auto_renew,
        )

        # 3. 原子性地锁定资源
        async with self.resource_registry.lock(resource.id):
            if resource.state != ResourceState.IDLE:
                raise ResourceUnavailableError("Resource no longer available")

            await self.resource_lifecycle.transition(resource, ResourceState.LEASED)
            resource.current_lease_id = lease.id
            self.leases[lease.id] = lease

        # 4. 启动租约监控
        asyncio.create_task(self._monitor_lease(lease))
        return lease

    async def release(self, lease_id: str, cleanup: bool = True):
        """释放租约"""
        lease = self.leases.get(lease_id)
        if not lease:
            return

        lease.state = LeaseState.RELEASED
        resource = await self.resource_registry.get(lease.resource_id)

        if resource:
            if cleanup:
                await self.resource_lifecycle.transition(resource, ResourceState.RELEASING)
                await self._cleanup_resource(resource)

            await self.resource_lifecycle.transition(resource, ResourceState.IDLE)
            resource.current_lease_id = None

        del self.leases[lease_id]

    async def renew(self, lease_id: str, extension_seconds: int = None) -> Lease:
        """续租"""
        lease = self.leases.get(lease_id)
        if not lease or lease.state != LeaseState.ACTIVE:
            raise LeaseError("Lease not found or not active")

        if lease.renewal_count >= lease.max_renewals:
            raise LeaseError("Max renewals exceeded")

        extension = extension_seconds or self.config.default_extension_seconds
        new_expiry = lease.expires_at + timedelta(seconds=extension)

        # 检查是否超过最大租约时长
        total_duration = (new_expiry - lease.acquired_at).total_seconds()
        if total_duration > lease.max_duration_seconds:
            raise LeaseError("Would exceed max lease duration")

        lease.expires_at = new_expiry
        lease.renewal_count += 1
        return lease
```

## 租约监控

```python
async def _monitor_lease(self, lease: Lease):
    """监控租约状态，自动续租或过期处理"""
    while lease.state == LeaseState.ACTIVE:
        await asyncio.sleep(1)

        if lease.is_expired():
            await self._handle_expired_lease(lease)
            break

        if lease.should_renew():
            try:
                await self.renew(lease.id)
            except LeaseError:
                await self._notify_lease_expiring(lease)
```

## 租约垃圾回收

```python
async def gc(self) -> LeaseGCStats:
    """清理无效租约"""
    stats = LeaseGCStats()

    for lease_id, lease in list(self.leases.items()):
        # 清理已释放/过期的租约
        if lease.state in [LeaseState.RELEASED, LeaseState.EXPIRED]:
            del self.leases[lease_id]
            stats.cleaned_count += 1

        # 清理孤儿租约（任务已不存在）
        if not await self.task_registry.exists(lease.task_id):
            await self.release(lease_id)
            stats.orphaned_count += 1

    return stats
```

## gRPC 接口

```protobuf
service LeaseManager {
    // 获取租约
    rpc Acquire(AcquireLeaseRequest) returns (AcquireLeaseResponse);

    // 续租
    rpc Renew(RenewLeaseRequest) returns (RenewLeaseResponse);

    // 释放租约
    rpc Release(ReleaseLeaseRequest) returns (ReleaseLeaseResponse);
}

message AcquireLeaseRequest {
    string task_id = 1;
    string step_id = 2;
    repeated string capabilities = 3;
    map<string, string> label_selector = 4;
    int32 duration_seconds = 5;
    int32 max_duration_seconds = 6;
    bool auto_renew = 7;
}

message AcquireLeaseResponse {
    Lease lease = 1;
    Resource resource = 2;
}
```

## 配置参考

```yaml
lease:
  default_duration_seconds: 300      # 默认租约时长 5 分钟
  max_duration_seconds: 3600         # 最大租约时长 1 小时
  default_extension_seconds: 300     # 默认续租时长
  renew_threshold_seconds: 30        # 续租阈值
  max_renewals: 10                   # 最大续租次数
  gc_interval_seconds: 60            # GC 间隔
```

## 相关文档

- [资源管理概述](./README.md)
- [资源池](./resource-pool.md)
- [资源清理](./resource-cleanup.md)
