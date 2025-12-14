# AgentScope Manus 多智能体执行平台

> 基于 **AgentScope** 构建的 Manus-like 多智能体执行平台。所有 **tools/skills** 封装为 **Agent**（Agent-as-a-Service），任何能力调用必须通过对应 Agent 完成。

## 核心目标

- 并发支持约 **100** 任务
- 同时调度 **多个浏览器、多个容器、多个虚拟机、多个手机**
- 强制 **可控、可审计、可回放、可恢复**

## 范围与非目标

### 范围（Scope）

- **多智能体协作**：规划、执行、验收、仲裁、数据处理
- **资源调度**：浏览器/容器/VM/手机统一管理、租约化（Lease）与并发控制
- **能力封装**：所有工具能力以 Agent 形式提供（General/Specialist 两类）
- **多模型选择**：父 Agent 可按任务/步骤指定模型策略
- **可观测性**：全链路 Trace/Log/Metric，证据标准化存储与回放
- **可恢复**：任务中断/续跑、失败重试、换资源重试、必要时重新规划

### 非目标（Non-goals）

- v1 不追求强视觉 GUI（可先提供 Web 控制台与 API）
- v1 不追求通用"自动生成所有技能"的工具市场
- v1 不追求完全的自治自学习闭环

## 设计原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | **Agent-as-a-Service** | 能力以 Agent 对外提供；不允许上层直连工具 |
| 2 | **契约优先** | 所有 Agent 调用必须声明 Intent、Return Spec、Success Criteria、Evidence Required |
| 3 | **资源租约化** | 执行型 Agent 必须持有 Lease 才能产生外部副作用 |
| 4 | **模型策略集中化** | 模型选择由策略器统一治理 |
| 5 | **可回放** | 执行型 Agent 必须返回 action log / replay_uri |
| 6 | **可观测** | 全链路 OTel；关键证据为一等公民 |
| 7 | **标准优先** | WebDriver/Appium/K8s/OTel/OpenAPI/gRPC |

## 技术标准

| 领域 | 标准 |
|------|------|
| 浏览器 | W3C WebDriver（主）+ CDP（补） |
| 手机 | Appium（W3C WebDriver 生态） |
| 容器 | OCI + Kubernetes |
| 可观测 | OpenTelemetry |
| API | OpenAPI（外部）+ gRPC（内部） |

## 快速导航

- [逻辑架构](./architecture.md)
- [里程碑与交付物](./roadmap.md)
- [架构决策记录](./adr/)

## 相关文档

- [Agent 系统设计](../01-agents/README.md)
- [编排调度系统](../02-orchestration/README.md)
- [契约定义](../11-contracts/README.md)
