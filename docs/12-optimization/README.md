# 优化建议

## 概述

技术评审结果与改进建议，重点关注：复用性、调用延迟、内存/资源回收、安全性、轻量化设计。

## 架构评分

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 架构完整性 | 4.5 | 分层清晰，覆盖全面 |
| 技术选型 | 4.5 | 标准优先原则执行到位 |
| 可扩展性 | 4.0 | 插件化设计良好，动态 DAG 需加强 |
| 可靠性设计 | 4.0 | 验证机制完善，故障恢复需细化 |
| 安全性设计 | 3.5 | 框架有，实现细节需补充 |
| 可操作性 | 3.5 | 契约复杂度高，需要简化版本 |

## 识别的问题与改进

| 问题 | 影响 | 改进方向 |
|------|------|----------|
| 层级过多导致延迟累积 | 完整请求可能经过 6+ 层调用 | 引入 Fast Path |
| Control Plane 单点风险 | Orchestrator/Router/Scheduler 高度集中 | 高可用设计 |
| CriticAgent 职责过重 | 同时负责验收、纠偏、资源切换、重规划 | 拆分为 ValidatorAgent + RecoveryAgent |
| 契约过于庞大 | AgentCall 包含 15+ 顶级字段 | 分层契约模板 |
| DAG 缺少动态重构能力 | replan 时无法修改执行中的 DAG | 增加 DAGMutator 组件 |

## 轻量化设计

### 核心与可选分离

```
核心模块（必需）:
├── Orchestrator
├── DAGScheduler
├── LeaseManager
└── AgentGateway

可选模块（按需加载）:
├── MemorySystem
├── NegotiatorAgent
├── VerificationSystem
└── ReplaySystem
```

### 延迟加载

```python
class LazyLoader:
    """延迟加载器"""
    _instances = {}

    @classmethod
    def get(cls, name: str) -> Any:
        if name not in cls._instances:
            cls._instances[name] = cls._load(name)
        return cls._instances[name]
```

### 对象池复用

```python
class ObjectPool:
    """对象池 - 减少创建/销毁开销"""

    def __init__(self, factory, min_size: int = 5, max_size: int = 50):
        self.pool = asyncio.Queue()
        self.factory = factory
        self.min_size = min_size
        self.max_size = max_size

    async def acquire(self) -> T:
        if self.pool.empty():
            return await self.factory.create()
        return await self.pool.get()

    async def release(self, obj: T):
        if self.pool.qsize() < self.max_size:
            await self.pool.put(obj)
```

## 复用性增强

### 原子能力

```python
# 定义原子能力
ATOMS = {
    'browser.navigate': NavigateAtom,
    'browser.click': ClickAtom,
    'browser.type': TypeAtom,
    'browser.screenshot': ScreenshotAtom,
    'browser.evidence': EvidenceAtom,
}
```

### 行为 Mixin

```python
class RetryMixin:
    """重试能力"""
    async def with_retry(self, func, max_retries=3):
        ...

class EvidenceCollectorMixin:
    """证据收集能力"""
    async def collect_evidence(self, types: List[str]) -> Evidence:
        ...

class ContextInjectorMixin:
    """上下文注入能力"""
    def inject_context(self, call: AgentCall, memory: MemoryContext):
        ...
```

## 延迟优化

### Fast Path

对于简单任务，跳过部分处理层：

```python
if task.complexity == 'simple':
    # 跳过 Negotiation、Voting 等
    result = await fast_execute(task)
else:
    result = await full_execute(task)
```

### 并行化

```python
# 并行执行独立步骤
results = await asyncio.gather(*[
    execute_step(step) for step in independent_steps
])
```

### 推测执行

```python
# 在高置信度情况下预先执行下一步
if current_step.confidence > 0.95:
    asyncio.create_task(speculative_execute(next_step))
```

### 延迟预算

```python
class LatencyBudget:
    """延迟预算管理"""
    def __init__(self, total_budget_ms: int):
        self.total = total_budget_ms
        self.spent = 0

    def allocate(self, step_count: int) -> int:
        return (self.total - self.spent) // step_count

    def record(self, latency_ms: int):
        self.spent += latency_ms
```

## 部署模式

| 模式 | 适用场景 | 资源需求 |
|-----|---------|---------|
| 单机开发 | 本地开发调试 | 4 CPU, 8GB RAM |
| 轻量部署 | 小规模生产 | 8 CPU, 16GB RAM |
| 标准部署 | 中等规模 | K8s 集群 |
| 高可用部署 | 大规模生产 | 多区域 K8s |

## 改进总结

| 维度 | 改进措施 |
|-----|---------|
| **内存回收** | 三级内存模型 + 任务级作用域 + 引用计数 + 压力响应 + 层级自动迁移 |
| **资源回收** | 状态机生命周期 + 租约自动续租/过期 + 类型化清理器 + 资源池弹性伸缩 |
| **轻量化** | 核心/可选分离 + 延迟加载 + 对象池复用 + 配置驱动裁剪 + 多部署模式 |
| **复用性** | 原子能力 + 行为 Mixin + 契约模板 + Step 模式库 |
| **延迟优化** | Fast Path + 并行化 + 推测执行 + 异步验证 + 延迟预算 |

## 相关文档

- [架构概述](../00-overview/architecture.md)
- [记忆系统](../04-memory/README.md)
- [资源管理](../03-resources/README.md)
