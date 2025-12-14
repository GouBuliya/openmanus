# AgentScope Manus 平台文档

> 多智能体执行平台设计与实现文档

## 文档索引

### 核心文档（Phase 1）

| 模块 | 说明 | 状态 |
|------|------|------|
| [00-overview](./00-overview/) | 项目概述、架构、里程碑 | ✅ 完成 |
| [01-agents](./01-agents/) | Agent 体系设计、调用契约 | ✅ 完成 |
| [02-orchestration](./02-orchestration/) | DAG 调度、Step 生命周期、执行流程 | ✅ 完成 |
| [11-contracts](./11-contracts/) | API 契约、gRPC 定义、OpenAPI | ✅ 完成 |

### 功能模块（Phase 2）

| 模块 | 说明 | 状态 |
|------|------|------|
| [03-resources](./03-resources/) | 资源管理、租约、资源池 | ✅ 完成 |
| [04-memory](./04-memory/) | 记忆系统、向量检索 | ✅ 完成 |
| [05-negotiation](./05-negotiation/) | 意图协商机制 | ✅ 完成 |
| [06-verification](./06-verification/) | 投票与对抗验证 | ✅ 完成 |

### 支撑模块（Phase 3）

| 模块 | 说明 | 状态 |
|------|------|------|
| [07-llm](./07-llm/) | 多模型策略 | ✅ 完成 |
| [08-evidence](./08-evidence/) | 证据系统 | ✅ 完成 |
| [09-security](./09-security/) | 安全治理 | ✅ 完成 |
| [10-observability](./10-observability/) | 可观测性 | ✅ 完成 |
| [12-optimization](./12-optimization/) | 优化建议 | ✅ 完成 |

### 附录

| 文档 | 说明 |
|------|------|
| [99-appendix/original-design-plan.md](./99-appendix/original-design-plan.md) | 完整原始设计文档 |
| [99-appendix/naming-conventions.md](./99-appendix/naming-conventions.md) | 命名规范 |
| [99-appendix/module-dependencies.md](./99-appendix/module-dependencies.md) | 模块依赖图 |

## 快速开始

1. **了解项目** → [00-overview/README.md](./00-overview/README.md)
2. **理解架构** → [00-overview/architecture.md](./00-overview/architecture.md)
3. **Agent 开发** → [01-agents/README.md](./01-agents/README.md)
4. **调度系统** → [02-orchestration/README.md](./02-orchestration/README.md)

## 技术栈

| 层级 | 技术 |
|-----|-----|
| 语言 | Python 3.11+ |
| Agent 框架 | AgentScope |
| API | FastAPI + gRPC |
| 数据库 | PostgreSQL + pgvector |
| 消息队列 | Kafka + Redis Streams |
| 浏览器 | Chrome DevTools MCP |
| 可观测性 | OpenTelemetry → Jaeger + Prometheus |

## 文档维护

- 所有文档使用 Markdown 格式
- 代码示例使用 Python
- 架构图使用 ASCII Art 或 Mermaid
- 保持文档与代码同步更新
