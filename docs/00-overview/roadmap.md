# 里程碑与交付物

## 里程碑（Roadmap）

### Milestone 0：契约与骨架（1-2 周）

- [ ] 完成三份契约：AgentCall / Registry / Lease
- [ ] 搭建 Orchestrator 状态机（最小闭环）
- [ ] OTel 基础接入 + Evidence Store

### Milestone 1：浏览器域闭环（2-4 周）

- [ ] BrowserAgent（CDP/MCP + WebDriver）
- [ ] 基础证据（截图/DOM/HAR/action_log）
- [ ] fanout 并行（多浏览器 context）
- [ ] Critic 验收与换资源重试

### Milestone 2：容器与数据处理（4-6 周）

- [ ] ContainerAgent（K8s Job）执行脚本任务
- [ ] 证据/工件回收与索引
- [ ] 基础配额/租户隔离

### Milestone 3：手机域（6-10 周）

- [ ] MobileAgent（Android 真机/模拟器）
- [ ] UI-tree/截图/录屏证据
- [ ] iOS 预留字段与驱动接口（XCUITest/WDA）

### Milestone 4：多 VM/桌面（10-14 周）

- [ ] VMDesktopAgent（SSH/RDP）
- [ ] 录屏与动作回放

### Milestone 5：AutoGLM 融合

- [ ] AutoGLM 作为"意图→动作计划"的上层生成器
- [ ] 底层执行仍走 Appium/WebDriver，保留回放与审计一致性

---

## 交付物清单（v1）

### API 层

- [ ] **OpenAPI**：Task/Session API（含 timeline/evidence/replay）
- [ ] **gRPC**：AgentGateway、CapabilityRegistry、LeaseManager

### 编排层

- [ ] **Orchestrator**：Step 状态机 + DAG Scheduler + Router + Policy

### Agent 层

- [ ] **General Agents**：Planner、Executor、Critic、Coordinator
- [ ] **Specialist Agents**：
  - [ ] BrowserAgent (CDP/MCP + WebDriver)
  - [ ] MobileAgent (Appium, Android)
  - [ ] ContainerAgent (K8s)

### 存储层

- [ ] **Evidence Store**：S3 存储 + Postgres 索引
- [ ] **State Store**：Postgres + Redis Cache

### 可观测性

- [ ] **OTel**：Trace/Log/Metric 接入
- [ ] **Dashboard**：基础仪表盘（Grafana）

### 高级功能

- [ ] **Memory System**：向量存储 + 记忆检索 + 经验沉淀
- [ ] **Intent Negotiation**：NegotiatorAgent + 意图解析 + 协商对话
- [ ] **Adversarial Verification**：VotingAgent + 多路验证 + 冲突仲裁

---

## 架构决策记录（ADR）

建议建立的 ADR 列表：

| ADR | 主题 | 状态 |
|-----|------|------|
| ADR-001 | Agent-as-a-Service 与禁止直连工具 | 待创建 |
| ADR-002 | WebDriver/Appium 作为标准执行入口 | 待创建 |
| ADR-003 | Lease 作为强制执行门禁 | 待创建 |
| ADR-004 | 证据与回放一等公民 | 待创建 |
| ADR-005 | OpenAPI 外部 + gRPC 内部 | 待创建 |

ADR 文档存放于 `./adr/` 目录。
