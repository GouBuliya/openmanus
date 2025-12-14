# OpenManus

基于 AgentScope 的多智能体执行平台

## 概述

OpenManus 是一个 **Agent-as-a-Service** 多智能体执行平台，提供：

- **DAG 拓扑调度** - 基于分层 Kahn 算法的任务编排
- **契约优先设计** - 所有交互通过显式 Pydantic 契约
- **资源租约管理** - 安全的资源访问控制
- **多模型 LLM 集成** - 支持 OpenAI、Anthropic、DeepSeek 等
- **全链路可观测性** - OpenTelemetry 集成

## 安装

```bash
# 使用 uv (推荐)
uv sync

# 开发模式
uv sync --dev
uv run pre-commit install
```

## 快速开始

```python
from openmanus import Task
from openmanus.orchestration import Orchestrator

# 创建任务
task = Task(
    id="task_001",
    tenant_id="tenant_001",
    user_input="在淘宝搜索 iPhone 15，对比前5个商品价格",
)

# 执行任务
orchestrator = Orchestrator()
result = await orchestrator.execute_task(task.id)
```

## 架构

```
┌─────────────────────────────────────────┐
│   API Layer (FastAPI + gRPC)            │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│   Orchestration (DAG Scheduler)         │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│   Agent Plane                           │
│   Planner | Executor | Critic | ...     │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│   Resource Plane (Lease Manager)        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│   Execution Plane                       │
│   Browser | Mobile | Container | VM     │
└─────────────────────────────────────────┘
```

## 核心概念

### AgentCall 契约

所有 Agent 调用必须符合 `AgentCall` 契约：

```python
from openmanus.core.contracts import AgentCall, ReturnSpec, SuccessCriteria

call = AgentCall(
    intent="搜索商品并获取价格",
    return_spec=ReturnSpec(
        schema_id="product_list",
        required_fields=["title", "price"],
    ),
    success_criteria=SuccessCriteria(
        conditions=["返回至少1个商品"],
        timeout_ms=30000,
    ),
    evidence_required=["screenshot", "dom_snapshot"],
    tracing=TracingContext(
        task_id="task_001",
        step_id="step_001",
        call_id="call_001",
    ),
)
```

### 资源租约

执行类 Agent 必须持有有效租约：

```python
from openmanus.resources import LeaseManager

lease = await lease_manager.acquire(
    LeaseRequest(
        task_id="task_001",
        step_id="step_001",
        resource_type=ResourceType.BROWSER,
        capabilities=["browser.navigate", "browser.screenshot"],
    )
)
```

## 开发

```bash
# 代码检查
make lint

# 格式化
make format

# 类型检查
make typecheck

# 运行测试
make test

# 启动开发服务器
make serve
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.13 |
| Agent 框架 | AgentScope |
| API | FastAPI + gRPC |
| 数据库 | PostgreSQL + pgvector |
| 消息队列 | Kafka + Redis |
| 可观测性 | OpenTelemetry |

## 项目结构

```
src/openmanus/
├── core/           # 核心抽象 (契约、接口、事件)
├── agents/         # Agent 实现
├── orchestration/  # 编排调度
├── resources/      # 资源管理
├── llm/            # LLM 集成
├── evidence/       # 证据系统
├── api/            # API 层
├── observability/  # 可观测性
├── config/         # 配置
└── di/             # 依赖注入
```

## License

MIT
