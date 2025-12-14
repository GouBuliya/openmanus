# 记忆生命周期管理

## 概述

完整的内存生命周期管理，支持分层存储、自动迁移、任务级作用域和压力响应。

## 生命周期管理器

```python
class MemoryLifecycleManager:
    """内存生命周期管理器"""

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.hot = RedisStore(config.redis)
        self.warm = PostgresStore(config.postgres)
        self.cold = S3Store(config.s3)
        self.registry = MemoryRegistry()

    async def store(self, key: str, value: Any, meta: MemoryMeta) -> MemoryEntry:
        """存储数据，自动选择初始层级"""
        entry = MemoryEntry(
            id=key,
            type=meta.type,
            created_at=datetime.utcnow(),
            last_accessed_at=datetime.utcnow(),
            access_count=0,
            size_bytes=self._calculate_size(value),
            ttl_seconds=meta.ttl_seconds,
            tier=self._select_initial_tier(meta),
            task_id=meta.task_id,
            evictable=meta.evictable,
        )

        await self._store_to_tier(entry.tier, key, value)
        await self.registry.register(entry)
        return entry

    async def get(self, key: str) -> Optional[Any]:
        """读取数据，自动更新访问统计"""
        entry = await self.registry.get(key)
        if not entry:
            return None

        if entry.is_expired():
            await self._evict(entry)
            return None

        value = await self._read_from_tier(entry.tier, key)

        # 更新访问统计（异步，不阻塞）
        asyncio.create_task(self._update_access_stats(entry))

        # 热点数据自动晋升
        if entry.tier != MemoryTier.HOT and entry.access_count > 10:
            asyncio.create_task(self._promote(entry))

        return value
```

## 层级迁移

### 降级 (Demote)

```python
async def _demote(self, entry: MemoryEntry):
    """降级到下一层"""
    value = await self._read_from_tier(entry.tier, entry.id)
    next_tier = self._get_next_tier(entry.tier)

    await self._store_to_tier(next_tier, entry.id, value)
    await self._delete_from_tier(entry.tier, entry.id)

    entry.tier = next_tier
    await self.registry.update(entry)
```

### 晋升 (Promote)

```python
async def _promote(self, entry: MemoryEntry):
    """晋升到上一层"""
    value = await self._read_from_tier(entry.tier, entry.id)
    prev_tier = self._get_prev_tier(entry.tier)

    await self._store_to_tier(prev_tier, entry.id, value)
    entry.tier = prev_tier
    await self.registry.update(entry)
```

### 迁移条件

```python
def should_demote(self) -> bool:
    """判断是否应降级到下一层"""
    idle_seconds = (datetime.utcnow() - self.last_accessed_at).total_seconds()
    if self.tier == MemoryTier.HOT:
        return idle_seconds > 300  # 5分钟未访问降级
    elif self.tier == MemoryTier.WARM:
        return idle_seconds > 86400  # 1天未访问降级
    return False
```

## 垃圾回收

```python
async def gc(self) -> GCStats:
    """垃圾回收主循环"""
    stats = GCStats()

    # 1. 过期回收
    expired = await self.registry.find_expired()
    for entry in expired:
        await self._evict(entry)
        stats.expired_count += 1
        stats.freed_bytes += entry.size_bytes

    # 2. 引用计数为 0 的条目回收
    orphaned = await self.registry.find_orphaned()
    for entry in orphaned:
        if entry.evictable:
            await self._evict(entry)
            stats.orphaned_count += 1
            stats.freed_bytes += entry.size_bytes

    # 3. 层级降级
    demotable = await self.registry.find_demotable()
    for entry in demotable:
        await self._demote(entry)
        stats.demoted_count += 1

    # 4. 容量压力回收（LRU）
    if await self._is_capacity_pressure():
        evicted = await self._evict_lru(target_free_ratio=0.2)
        stats.pressure_evicted_count = len(evicted)

    return stats
```

## 任务级作用域

```python
class TaskMemoryScope:
    """任务级内存作用域，支持级联回收"""

    def __init__(self, task_id: str, memory_manager: MemoryLifecycleManager):
        self.task_id = task_id
        self.memory_manager = memory_manager
        self.owned_keys: Set[str] = set()

    async def __aenter__(self):
        await self.memory_manager.registry.create_scope(self.task_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def store(self, key: str, value: Any, **kwargs) -> MemoryEntry:
        entry = await self.memory_manager.store(
            key=f"{self.task_id}:{key}",
            value=value,
            meta=MemoryMeta(task_id=self.task_id, **kwargs),
        )
        self.owned_keys.add(entry.id)
        return entry

    async def cleanup(self, keep_evidence: bool = True):
        """清理任务相关的所有内存"""
        for key in self.owned_keys:
            entry = await self.memory_manager.registry.get(key)
            if entry:
                if keep_evidence and entry.type == MemoryType.EVIDENCE:
                    await self.memory_manager._demote_to_cold(entry)
                else:
                    entry.ref_count -= 1
                    if entry.ref_count <= 0:
                        await self.memory_manager._evict(entry)

        self.owned_keys.clear()
```

### 使用示例

```python
async def execute_task(task: Task):
    async with TaskMemoryScope(task.id, memory_manager) as scope:
        await scope.store('context', task.context, ttl_seconds=3600)
        await scope.store('intermediate_results', results, ttl_seconds=1800)
        result = await do_work()
    # <- 作用域结束时自动调用 cleanup()
```

## 内存压力响应

```python
class MemoryPressureHandler:
    """内存压力处理器"""

    PRESSURE_LEVELS = {
        'normal': 0.7,    # < 70% 使用率
        'warning': 0.8,   # 70-80%
        'critical': 0.9,  # 80-90%
        'emergency': 0.95 # > 95%
    }

    async def monitor(self):
        while True:
            usage = await self.get_memory_usage()
            level = self._get_pressure_level(usage)

            if level != 'normal':
                await self._handle_pressure(level, usage)

            await asyncio.sleep(self.config.check_interval_seconds)

    async def _handle_pressure(self, level: str, usage: float):
        if level == 'warning':
            # 警告级：执行 GC，降低新任务内存配额
            await self.memory_manager.gc()
            self.config.per_task_memory_limit *= 0.8

        elif level == 'critical':
            # 严重级：强制降级不活跃数据，暂停新任务
            await self._force_demote_inactive()
            await self.scheduler.pause_new_tasks()
            await self.alert('memory_critical', usage=usage)

        elif level == 'emergency':
            # 紧急级：LRU 淘汰，取消非关键任务
            await self.memory_manager._evict_lru(target_free_ratio=0.3)
            await self.scheduler.cancel_non_critical_tasks()
            await self.alert('memory_emergency', usage=usage, severity='critical')
```

### 压力级别响应

| 级别 | 使用率 | 响应动作 |
|-----|-------|---------|
| Normal | < 70% | 正常运行 |
| Warning | 70-80% | GC + 降低配额 |
| Critical | 80-90% | 降级 + 暂停新任务 + 告警 |
| Emergency | > 95% | LRU 淘汰 + 取消任务 + 紧急告警 |

## 条目淘汰

```python
async def _evict(self, entry: MemoryEntry):
    """淘汰单个条目"""
    if entry.ref_count > 0:
        raise MemoryError(f"Cannot evict entry {entry.id} with ref_count={entry.ref_count}")

    await self._delete_from_tier(entry.tier, entry.id)
    await self.registry.unregister(entry.id)
    await self.event_bus.emit(MemoryEvictedEvent(entry))
```

## 相关文档

- [记忆系统概述](./README.md)
- [记忆类型](./memory-types.md)
- [配置参考](./memory-config.md)
