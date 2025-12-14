# 资源池

## 概述

资源池统一管理各类执行资源，支持预热、弹性伸缩和健康检查。

## 资源池管理器

```python
class ResourcePool:
    """资源池管理"""

    def __init__(self, config: PoolConfig):
        self.config = config
        self.pools: Dict[ResourceType, TypedPool] = {}
        self._init_pools()

    async def warm_up(self):
        """预热资源池 - 启动时初始化最小资源数"""
        tasks = [pool.ensure_min_size() for pool in self.pools.values()]
        await asyncio.gather(*tasks)

    async def acquire(self, resource_type: ResourceType, timeout_ms: int = 5000) -> Resource:
        """获取资源"""
        pool = self.pools.get(resource_type)
        if not pool:
            raise ValueError(f"Unknown resource type: {resource_type}")

        try:
            return await asyncio.wait_for(pool.acquire(), timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            # 超时时尝试扩容
            if pool.can_scale_up():
                return await pool.scale_up_one()
            raise ResourceUnavailableError("Pool exhausted")

    async def release(self, resource: Resource):
        """释放资源"""
        pool = self.pools.get(resource.type)
        if pool:
            await self.cleaner.cleanup(resource)
            await pool.release(resource)
```

## 类型化资源池

```python
class TypedPool:
    """类型化资源池"""

    def __init__(self, resource_type: ResourceType, min_size: int, max_size: int, **kwargs):
        self.resource_type = resource_type
        self.min_size = min_size
        self.max_size = max_size

        self.idle: asyncio.Queue[Resource] = asyncio.Queue()
        self.in_use: Set[str] = set()
        self.all_resources: Dict[str, Resource] = {}
        self._lock = asyncio.Lock()

    @property
    def utilization(self) -> float:
        """资源利用率"""
        if len(self.all_resources) == 0:
            return 0
        return len(self.in_use) / len(self.all_resources)

    async def acquire(self) -> Resource:
        """获取资源"""
        resource = await self.idle.get()
        self.in_use.add(resource.id)
        return resource

    async def release(self, resource: Resource):
        """归还资源"""
        self.in_use.discard(resource.id)
        await self.idle.put(resource)

    async def scale_up(self, count: int = 1):
        """扩容"""
        async with self._lock:
            for _ in range(count):
                if len(self.all_resources) >= self.max_size:
                    break
                resource = await self._create_resource()
                self.all_resources[resource.id] = resource
                await self.idle.put(resource)

    async def scale_down(self, count: int = 1):
        """缩容"""
        async with self._lock:
            for _ in range(count):
                if len(self.all_resources) <= self.min_size:
                    break
                if self.idle.empty():
                    break
                resource = await self.idle.get()
                await self._destroy_resource(resource)
                del self.all_resources[resource.id]
```

## 资源池维护

```python
async def maintain(self):
    """资源池维护循环"""
    while True:
        for pool in self.pools.values():
            # 1. 健康检查
            unhealthy = await pool.health_check()
            for resource in unhealthy:
                await pool.remove(resource)

            # 2. 弹性伸缩
            if pool.utilization > pool.scale_up_threshold:
                await pool.scale_up()
            elif pool.utilization < pool.scale_down_threshold:
                await pool.scale_down()

            # 3. 清理过期空闲资源
            expired = await pool.get_expired_idle()
            for resource in expired:
                await pool.remove(resource)

        await asyncio.sleep(self.config.maintain_interval_seconds)
```

## 弹性伸缩策略

### 扩容触发条件

| 条件 | 阈值 | 动作 |
|-----|------|-----|
| 利用率高 | `utilization > 0.8` | 扩容 25% |
| 队列等待 | `wait_time > 5s` | 扩容 1 个 |
| 超时请求 | `timeout && can_scale` | 扩容 1 个 |

### 缩容触发条件

| 条件 | 阈值 | 动作 |
|-----|------|-----|
| 利用率低 | `utilization < 0.3` | 缩容至 min_size |
| 空闲过久 | `idle_time > 10min` | 释放该资源 |

### 伸缩限制

```python
@dataclass
class ScalingPolicy:
    scale_up_threshold: float = 0.8      # 扩容阈值
    scale_down_threshold: float = 0.3    # 缩容阈值
    scale_up_step: int = 2               # 每次扩容数量
    scale_down_step: int = 1             # 每次缩容数量
    cooldown_seconds: int = 60           # 伸缩冷却时间
    max_idle_seconds: int = 600          # 最大空闲时间
```

## 资源池配置

```yaml
pools:
  browser:
    min_size: 5
    max_size: 50
    scale_up_threshold: 0.8
    scale_down_threshold: 0.3
    max_idle_seconds: 600
    health_check_interval: 30

  container:
    min_size: 2
    max_size: 20
    scale_up_threshold: 0.7
    scale_down_threshold: 0.2
    max_idle_seconds: 300

  mobile:
    min_size: 0          # 真机不预热
    max_size: 10
    scale_up_threshold: 0.9
    scale_down_threshold: 0.5

  vm:
    min_size: 1
    max_size: 5
    scale_up_threshold: 0.8
    scale_down_threshold: 0.3
    max_idle_seconds: 1800

global:
  maintain_interval_seconds: 30
  health_check_timeout_ms: 5000
```

## 健康检查

```python
async def health_check(self) -> List[Resource]:
    """健康检查，返回不健康资源列表"""
    unhealthy = []

    for resource in self.all_resources.values():
        try:
            is_healthy = await asyncio.wait_for(
                self._check_resource_health(resource),
                timeout=self.config.health_check_timeout_ms / 1000
            )
            if not is_healthy:
                unhealthy.append(resource)
        except asyncio.TimeoutError:
            unhealthy.append(resource)

    return unhealthy

async def _check_resource_health(self, resource: Resource) -> bool:
    """资源类型特定的健康检查"""
    if resource.type == ResourceType.BROWSER:
        return await self._check_browser_health(resource)
    elif resource.type == ResourceType.CONTAINER:
        return await self._check_container_health(resource)
    # ... 其他类型
```

## 指标监控

```python
# 资源池指标
pool_size_total = Gauge('resource_pool_size_total', 'Pool total size', ['type'])
pool_idle_count = Gauge('resource_pool_idle_count', 'Pool idle count', ['type'])
pool_in_use_count = Gauge('resource_pool_in_use_count', 'Pool in use count', ['type'])
pool_utilization = Gauge('resource_pool_utilization', 'Pool utilization', ['type'])

# 伸缩事件
scale_events_total = Counter('resource_pool_scale_events_total', 'Scale events', ['type', 'direction'])
```

## 相关文档

- [资源管理概述](./README.md)
- [租约管理](./lease-manager.md)
- [资源清理](./resource-cleanup.md)
