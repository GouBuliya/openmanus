# 模块依赖图

## 核心依赖关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        模块依赖（轻量化设计）                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        核心模块 (必需)                                │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │   │
│  │  │  Orchestrator │──│ DAGScheduler  │──│ LeaseManager  │            │   │
│  │  │  (编排调度)    │  │  (DAG 调度)   │  │  (租约管理)    │            │   │
│  │  └───────┬───────┘  └───────────────┘  └───────────────┘            │   │
│  │          │                                                           │   │
│  │          ▼                                                           │   │
│  │  ┌───────────────┐  ┌───────────────┐                               │   │
│  │  │ AgentGateway  │──│  AgentRouter  │                               │   │
│  │  │  (Agent 网关)  │  │  (能力路由)   │                               │   │
│  │  └───────────────┘  └───────────────┘                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        可选模块 (按需加载)                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Negotiator  │  │  Voting     │  │MemorySystem │  │ WebConsole  │ │   │
│  │  │ (意图协商)   │  │ (多Agent验证)│  │ (长期记忆)   │  │ (控制台)    │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 模块分类

### 核心模块（必需）

| 模块 | 职责 | 依赖 |
|-----|------|-----|
| Orchestrator | 任务编排、状态管理 | DAGScheduler, LeaseManager |
| DAGScheduler | DAG 拓扑调度 | - |
| LeaseManager | 资源租约管理 | ResourceRegistry |
| AgentGateway | Agent 调用入口 | AgentRouter |
| AgentRouter | 能力路由 | CapabilityRegistry |

### 可选模块

| 模块 | 职责 | 启用条件 |
|-----|------|---------|
| NegotiatorAgent | 意图协商 | `negotiation.enabled=true` |
| VotingAgent | 多 Agent 验证 | `verification.mode=voting` |
| MemorySystem | 长期记忆 | `memory.enabled=true` |
| WebConsole | Web 控制台 | `console.enabled=true` |

## 依赖注入

```python
class DependencyContainer:
    """依赖注入容器"""

    def __init__(self, config: Config):
        # 核心模块（始终加载）
        self.lease_manager = LeaseManager(config)
        self.dag_scheduler = DAGScheduler(config)
        self.orchestrator = Orchestrator(config)

        # 可选模块（按需加载）
        self.memory_manager = None
        self.negotiator = None
        self.voting_agent = None

    def get_memory_manager(self) -> MemoryManager:
        if self.memory_manager is None:
            self.memory_manager = MemoryManager(self.config)
        return self.memory_manager
```

## 配置驱动裁剪

```yaml
# 最小配置
modules:
  core:
    enabled: true
  negotiation:
    enabled: false
  verification:
    enabled: false
  memory:
    enabled: false

# 完整配置
modules:
  core:
    enabled: true
  negotiation:
    enabled: true
  verification:
    enabled: true
    mode: voting
  memory:
    enabled: true
```

## 部署拓扑

### 单机模式

```
┌─────────────────────────────┐
│      All-in-One             │
│  ┌─────┐ ┌─────┐ ┌─────┐   │
│  │ API │ │Orch │ │Agent│   │
│  └─────┘ └─────┘ └─────┘   │
└─────────────────────────────┘
```

### 微服务模式

```
┌─────────┐  ┌─────────┐  ┌─────────┐
│   API   │  │  Orch   │  │  Agent  │
│ Gateway │  │ Service │  │ Service │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  │
           ┌──────┴──────┐
           │   Message   │
           │    Queue    │
           └─────────────┘
```
