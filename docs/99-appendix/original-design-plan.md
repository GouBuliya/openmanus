# AgentScope Manus 多智能体执行平台：框架设计 Plan（v1）

> 目标：基于 **AgentScope** 构建一个 Manus-like 的多智能体执行平台。平台将所有 **tools/skills** 封装为 **Agent**（Agent-as-a-Service），任何能力调用必须通过对应 Agent 完成。平台支持并发约 **100**，可同时调度 **多个浏览器、多个容器、多个虚拟机、多个手机（真机/模拟器，预留 iOS）**。  
> 关键约束：尽量采用通用标准（WebDriver/Appium/K8s/OTel/OpenAPI/gRPC 等），强制“可控、可审计、可回放、可恢复”。

---

## 1. 范围与非目标

### 1.1 范围（Scope）
- 多智能体协作：规划、执行、验收、仲裁、数据处理等。
- 资源调度：浏览器/容器/VM/手机统一管理、租约化（Lease）与并发控制。
- 能力封装：所有工具能力以 **Agent** 形式提供（General/Specialist 两类）。
- 多模型选择：父 Agent 可按任务/步骤指定模型策略；子 Agent 可在预算与策略内执行。
- 可观测性：全链路 Trace/Log/Metric，证据（Evidence）标准化存储与回放。
- 可恢复：任务中断/续跑、失败重试、换资源重试、必要时重新规划（Replan）。

### 1.2 非目标（Non-goals）
- 不在 v1 追求强视觉 GUI（可先提供 Web 控制台与 API）。
- 不在 v1 追求通用“自动生成所有技能”的工具市场（可先内部注册）。
- 不在 v1 追求完全的自治自学习闭环（可先做可观测 + 规则优化）。

---

## 2. 总体原则（Design Principles）

1. **Agent-as-a-Service（AaaS）**：能力以 Agent 对外提供；不允许上层直连工具。
2. **契约优先（Contract-first）**：所有 Agent 调用必须显式声明：
   - 做什么（Intent）
   - 要返回什么（Return Spec / Output Schema）
   - 如何验收（Success Criteria）
   - 必须证据（Evidence Required）
3. **资源租约化（Lease Required）**：执行型 Agent 必须持有 Lease 才能产生外部副作用。
4. **模型策略集中化（Model Policy）**：模型选择由策略器统一治理；调用可覆盖但需受预算约束。
5. **可回放（Replayable）**：执行型 Agent 必须返回 action log / replay_uri（可复现/审计）。
6. **可观测（Observable）**：全链路 OTel；关键证据（截图/录屏/DOM/UI-tree/HAR）为一等公民。
7. **标准优先（Standards-first）**：
   - 浏览器：W3C WebDriver（主）+ CDP（补）
   - 手机：Appium（W3C WebDriver 生态），预留 iOS（XCUITest）
   - 容器：OCI + Kubernetes
   - 可观测：OpenTelemetry
   - API：OpenAPI（外部）+ gRPC（内部）

---

## 3. 逻辑架构（Logical Architecture）

### 3.1 分层视图
- **UI / Client**
  - Web Console（可选）：任务提交、时间线、证据浏览、回放、告警
  - SDK / CLI：提交任务、订阅事件、导出报告
- **Control Plane（控制面）**
  - Task/Session API（OpenAPI）
  - Orchestrator（任务/步骤状态机）
  - Router（能力路由，Agent 选择）
  - Scheduler（并发控制、队列、优先级）
  - Policy Engine（权限、配额、网络/文件策略、密钥域）
- **Agent Plane（智能体面，AgentScope）**
  - PlannerAgent：生成/更新步骤（Steps）
  - TaskExecutorAgent：执行调度（调用专用 Agent）
  - CriticAgent：验收/纠偏（重试/换资源/重规划）
  - CoordinatorAgent（可选）：多 Agent 仲裁与结果合并
- **Resource Plane（资源面）**
  - Capability Registry（能力/Agent 注册）
  - Resource Registry（资源登记：浏览器节点/手机/VM/容器）
  - Lease Manager（租约分配/续租/回收）
- **Execution Plane（执行面）**
  - Specialist Agents（Browser/Mobile/Container/VM…）
  - Drivers（WebDriver/CDP/Appium/K8s/SSH…）
  - Evidence Store（S3 兼容对象存储）
  - State Store（Postgres）+ Cache/Queue（Redis/Kafka/NATS）

### 3.2 核心数据流（简化）
1. 用户提交 Task → Task API 创建 Task
2. PlannerAgent 生成 Steps（包含 capability、return_spec、success_criteria、evidence_required、fanout）
3. Orchestrator 入队 Steps → Scheduler 按并发与配额调度
4. Router 为每个 Step 选择目标 Specialist Agent + 申请 Lease
5. TaskExecutorAgent 发起 AgentCall（含 lease_id、model_profile、return_spec…）
6. Specialist Agent 执行并返回结果与证据引用 → Critic 验收 → 进入下一步或重试/重规划
7. 全流程产出 Trace/Evidence，可回放与审计

---

## 4. Agent 体系设计

### 4.1 Agent 分类

#### A. 通用执行 Agent（General Executor Agents）
- **PlannerAgent**
  - 输入：用户目标、上下文、历史步骤
  - 输出：Steps（计划），每步显式声明能力与返回要求
- **TaskExecutorAgent**
  - 输入：Step
  - 行为：只负责调用 Specialist Agents（不直连工具）
  - 输出：StepResult（汇总）
- **CriticAgent**
  - 输入：Step、Result、Evidence
  - 输出：Decision（accept/retry/switch_resource/replan/needs_user）
- **CoordinatorAgent（可选）**
  - 适用于：并行子任务合并、冲突仲裁、投票/一致性检查

#### B. 专用执行 Agent（Specialist Executor Agents）
- **BrowserAgent**
  - 统一浏览器域：WebDriver 优先、必要时 CDP/MCP
  - 内部可二级路由：
    - WebDriverAgent
    - ChromeDevtoolsMcpAgent（例如“chrome devtools mcp”能力）
- **MobileAgent**
  - Appium 标准执行入口（Android 真机/模拟器；iOS XCUITest 预留）
  - 可选叠加 AutoGLM：用于“意图→动作计划”，底层仍由 Appium 执行以保证回放
- **ContainerAgent**
  - K8s Job/Pod 执行、工件产出、日志采集
- **VMDesktopAgent**
  - SSH/RDP/WinRM/VNC 等；可运行桌面自动化工具
- **DataOpsAgent（可选专用）**
  - 结构化抽取、文件处理、格式转换（可低风险无 Lease）

### 4.2 Agent 对外契约（强制）
每次 Agent 调用必须包含：
- **intent**：要做什么
- **return_spec**：要返回什么（schema_id + fields）
- **success_criteria**：如何验收
- **evidence_required**：必须产出的证据类型
- **constraints**：允许域名/禁止动作/时间预算/密钥域等
- **model_profile**：模型选择策略与预算
- **lease_id**：执行型 Agent 必需（产生副作用/访问资源）

> 任何 Specialist Agent 必须返回：`outputs + evidence + metrics + replay_uri`。

---

## 5. 统一契约与标准

### 5.1 外部 API（OpenAPI）
- `POST /tasks` 创建任务
- `POST /tasks/{id}/interrupt` 中断
- `POST /tasks/{id}/resume` 恢复
- `GET /tasks/{id}` 查询状态
- `GET /tasks/{id}/timeline` 时间线（steps/events）
- `GET /tasks/{id}/evidence` 证据索引（含下载链接/权限校验）
- `GET /tasks/{id}/replay` 回放入口（按 step 选择）

### 5.2 内部调用（gRPC）
- `AgentGateway.Invoke/InvokeStream`：Agent 调用与流式回传
- `CapabilityRegistry`：Agent 能力注册与发现
- `LeaseManager`：资源租约
- `EventBus`（可选）：CloudEvents/流式事件

### 5.3 执行标准
- 浏览器：**W3C WebDriver（主）**；需要更细能力时：**CDP**（Chromium）
- 手机：**Appium（W3C WebDriver 生态）**
  - Android：UiAutomator2
  - iOS 预留：XCUITest（WDA 管理）
  - 模拟器：同 Appium 接口
- 容器：**Kubernetes + OCI**
- 可观测：**OpenTelemetry**
- 事件：建议 **CloudEvents** 作为状态变更事件封装（可选）

---

## 6. 资源与调度（并发 100）

### 6.1 资源模型（Resource）
资源统一登记，字段参考 K8s label 思路：
- `resource_id`
- `type`: browser | mobile | container | vm
- `capabilities[]`
- `labels{}`：region、os、kind(real/sim)、browser、tenant…
- `limits{}`：concurrency、cpu、mem
- `health`：ok/degraded/down
- `endpoints{}`：
  - browser: webdriver_url / cdp_url
  - mobile: appium_url
  - container: namespace/job
  - vm: ssh/rdp/winrm

### 6.2 租约（Lease）
执行前必须 Acquire Lease：
- `lease_id`, `resource_id`, `expires_at`
- 绑定 `policy`（网络/文件/密钥域）
- 支持 `quantity`（fanout 并行）

### 6.3 调度策略（建议默认）
- 全局并发：**100 running steps**（可配置）
- 分类型并发：
  - 手机：每台设备 `concurrency=1`（真机），模拟器可 1~2
  - 浏览器节点：按 CPU/内存配置 `max_contexts`
- 队列优先级：interactive > batch
- 失败策略：
  1) retry（幂等/安全前提）
  2) switch_resource（换设备/换节点更有效）
  3) replan（Critic 触发）
- 反亲和：同 Step fanout 副本尽量分配不同 resource_id

---

## 7. Step 设计与 DAG 拓扑调度

> 基于论文《基于有向无环图拓扑调度的人工智能代理任务编排系统》，采用**层级化 Kahn 算法**实现任务编排，支持层内并行、层间串行，最大化并行度。

### 7.1 DAG 调度核心原理

#### 7.1.1 层级化 Kahn 算法
- **核心思想**：将 DAG 按拓扑顺序分层，同层任务互不依赖可并行执行
- **时间复杂度**：O(V + E)，V=节点数，E=边数
- **调度延迟**：<10ms（500 任务规模）
- **理论最优**：层数等于 DAG 中最长路径的节点数（Mirsky 定理）

```
算法流程：
1. 构建依赖图 G 和反向图 G'
2. 计算每个节点的入度 in_degree[v] = |v.deps|
3. 初始化队列 Q ← {v | in_degree[v] = 0}
4. while Q 非空:
     current_level ← Q 中所有节点（同层并行）
     对每个 v ∈ current_level:
       处理 v，更新下游节点入度
       若 in_degree[u] = 0 则加入 Q
5. 输出：[[Level0], [Level1], ..., [LevelK]]
```

#### 7.1.2 四种 DAG 依赖模式

| 模式 | 结构 | 典型场景 |
|------|------|----------|
| **线性链** | A → B → C | 思维链推理、顺序审核 |
| **扇入** | A, B, C → D | 多源数据整合、综合评估 |
| **扇出** | A → B, C, D | 并行分析、数据分发 |
| **菱形** | A → {B, C} → D | Map-Reduce、多工具并行后汇总 |

#### 7.1.3 上下文自动注入机制
```python
def inject_upstream_results(task: Dict) -> Dict:
    """将上游任务结果自动注入到当前任务的 handoff.context"""
    for dep_id in task.get('deps', []):
        if dep_id in task_results:
            result = task_results[dep_id]
            context_snippet = f"【上游任务结果】ID: {dep_id}\n{result}"
            task['handoff']['context'] += context_snippet
    return task
```

**优势**：
- 数据流自动化管理
- 任务间松耦合
- 执行逻辑与数据传递分离

### 7.2 Step 必含字段（DAG 增强版）

```python
Step = {
    # === 基础标识 ===
    'id': str,                        # 步骤唯一标识
    'title': str,                     # 步骤标题

    # === DAG 依赖（核心字段）===
    'deps': List[str],                # 依赖的步骤 ID 列表

    # === 能力要求 ===
    'capabilities_required': List[str],
    'label_selector': Dict,           # 资源标签选择器

    # === 并行控制 ===
    'fanout': int,                    # 并行副本数（单步内）
    'anti_affinity': bool,            # 副本分配到不同资源

    # === 执行控制 ===
    'idempotency_key': str,           # 幂等键（重试保护）
    'timeout_ms': int,                # 超时时间

    # === 输出规范 ===
    'return_spec': {
        'schema_id': str,
        'required_fields': List[str],
    },
    'success_criteria': str,
    'evidence_required': List[str],   # screenshot/video/dom_snapshot/...

    # === 约束 ===
    'constraints': {
        'no_purchase': bool,
        'allowed_domains': List[str],
        'time_budget_ms': int,
        'cost_budget_usd': float,
    },

    # === 执行上下文（Handoff）===
    'handoff': {
        'objective': str,             # 任务目标
        'context': str,               # 上下文（自动注入上游结果）
        'inputs': List[str],          # 需要提取的数据字段
        'instructions': List[str],    # 执行步骤
    },
}
```

### 7.3 DAG 调度器实现

```python
class DAGScheduler:
    def __init__(self, steps: List[Dict]):
        self.steps = {s['id']: s for s in steps}
        self.results = {}

    def topological_sort(self) -> List[List[str]]:
        """层级化拓扑排序：返回 [[level0_ids], [level1_ids], ...]"""
        dep_graph = {s['id']: s.get('deps', []) for s in self.steps.values()}
        in_degree = {sid: len(deps) for sid, deps in dep_graph.items()}
        reverse_graph = defaultdict(list)
        for sid, deps in dep_graph.items():
            for dep_id in deps:
                reverse_graph[dep_id].append(sid)

        levels = []
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        processed = set()

        while queue:
            current_level = list(queue)
            queue.clear()
            levels.append(current_level)

            for step_id in current_level:
                processed.add(step_id)
                for dependent in reverse_graph[step_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(processed) != len(self.steps):
            raise ValueError("检测到循环依赖")

        return levels

    async def execute(self) -> Dict:
        """层内并行、层间串行执行"""
        levels = self.topological_sort()

        for level_idx, level_ids in enumerate(levels):
            # 层内并行执行
            tasks = []
            for step_id in level_ids:
                step = self.inject_upstream_results(self.steps[step_id])
                tasks.append(self.execute_step(step))

            results = await asyncio.gather(*tasks)

            for step_id, result in zip(level_ids, results):
                self.results[step_id] = result

        return self.results
```

### 7.4 Step 生命周期（状态机）

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
PENDING → WAITING_DEPS → LEASED → RUNNING → SUCCEEDED        │
                              │       │                       │
                              │       ├─→ FAILED_RETRYABLE ──→┤
                              │       │         │             │
                              │       │         ▼             │
                              │       │      RETRYING ────────┘
                              │       │
                              │       ├─→ FAILED_RESOURCE → SWITCHING_RESOURCE
                              │       │
                              │       ├─→ FAILED_FATAL → FAILED
                              │       │
                              │       └─→ NEEDS_USER（验证码/二次确认）
                              │
                              └─→ LEASE_TIMEOUT → PENDING（重新排队）
```

**新增状态**：
- `WAITING_DEPS`：等待上游依赖完成（DAG 调度引入）
- `LEASE_TIMEOUT`：租约超时，需重新申请

### 7.5 DAG 合法性验证

```python
def validate_dag(steps: List[Dict]) -> Dict:
    """验证 DAG 结构合法性"""
    task_ids = {s['id'] for s in steps}
    issues = []

    for step in steps:
        # 检查依赖存在性
        for dep_id in step.get('deps', []):
            if dep_id not in task_ids:
                issues.append(f"步骤 {step['id']} 依赖不存在的 {dep_id}")

        # 检查自依赖
        if step['id'] in step.get('deps', []):
            issues.append(f"步骤 {step['id']} 存在自依赖")

    # 检查循环依赖（通过拓扑排序）
    try:
        DAGScheduler(steps).topological_sort()
    except ValueError as e:
        issues.append(str(e))

    return {
        'valid': len(issues) == 0,
        'issues': issues,
    }
```

---

## 8. 多模型策略（Model Policy）

### 8.1 策略器职责
- 根据 task/step 类型注入默认 model_profile：
  - plan：高推理（质量优先）
  - execute：低成本/低延迟（能完成即可）
  - critic：高精度（避免误判完成）
- 根据风险与副作用升级模型与审计：
  - 涉及下单/转账/发送消息：强制双重验收（Critic + Policy）
- 根据预算限制（max_cost/max_latency）做降级/拒绝

### 8.2 子 Agent 选择模型的边界
- 父 Agent 指定 preferred_models 与 policy；子 Agent 可在列表内选择
- 子 Agent 必须回传 `metrics.cost_usd/latency_ms/tokens` 用于闭环优化

---

## 9. 证据与回放（Evidence & Replay）

### 9.1 证据类型（统一枚举）
- screenshot / video
- dom_snapshot / network_har
- ui_tree（手机控件树）
- console_log / action_log
- file_artifact（下载文件/生成报表）

### 9.2 证据存储
- Evidence Store：S3 兼容对象存储
- Evidence Index：Postgres 保存引用、权限、元数据、归属 task/step/call

### 9.3 回放（Replay）
- Specialist Agent 必须返回 `replay_uri`：
  - 浏览器：actions + selectors + timings（或脚本引用）
  - 手机：WebDriver commands / action plan
  - 容器：镜像+命令+参数+工件
  - VM：命令序列/脚本/会话录屏

---

## 10. 安全与治理（Policy & Guardrails）

### 10.1 最小权限与密钥管理
- Secret 通过 `vault://` 引用，按 `secrets_scope` 下发给必要的 Specialist Agent
- 上层 Agent 不直接接触明文凭据（只拿到状态证明/引用）

### 10.2 网络与文件系统策略
- `allowed_domains` 白名单
- 出网策略：按 task/tenant 控制
- 文件系统策略：可读写路径、挂载点、上传/下载隔离

### 10.3 高风险操作门禁
- `constraints.flags.no_purchase=true` 等硬门槛
- 若允许购买/发送：需要“二次确认”或“人审”步骤（NEEDS_USER）

---

## 11. 可观测性（Observability）

### 11.1 OpenTelemetry
- Trace：task_id/step_id/call_id 作为核心 span 属性
- Logs：结构化日志（JSON），关联 trace_id
- Metrics：并发、队列长度、失败率、重试次数、成本、资源利用率

### 11.2 事件流（可选 CloudEvents）
- Step 状态变更、Lease acquire/release、Agent 调用结果、告警
- 便于 UI 实时更新与外部系统订阅

---

## 12. 代码与模块划分（Repo Layout）

```
manus-platform/
├─ api/                      # OpenAPI: task/session/admin
│   ├─ tasks.py              # Task CRUD + timeline + evidence
│   ├─ negotiation.py        # 意图协商 API
│   └─ admin.py              # 管理接口
│
├─ orchestrator/             # 编排与调度
│   ├─ dag_scheduler.py      # 【新增】层级化 Kahn DAG 调度器
│   ├─ context_injector.py   # 【新增】上下文自动注入
│   ├─ state_machine.py      # Step 状态机
│   ├─ router.py             # 能力路由
│   └─ policy.py             # 策略引擎
│
├─ agentscope_core/          # 核心 Agent（只决策不直连工具）
│   ├─ planner.py            # PlannerAgent
│   ├─ executor.py           # TaskExecutorAgent
│   ├─ critic.py             # CriticAgent
│   ├─ coordinator.py        # CoordinatorAgent
│   ├─ negotiator.py         # 【新增】NegotiatorAgent（意图协商）
│   └─ voting.py             # 【新增】VotingAgent（投票/对抗验证）
│
├─ memory/                   # 【新增】长期记忆系统
│   ├─ store.py              # Memory Store（向量 + 结构化）
│   ├─ retriever.py          # 记忆检索
│   ├─ updater.py            # 记忆更新
│   ├─ embeddings.py         # 向量嵌入
│   └─ schemas.py            # 记忆 Schema 定义
│
├─ contracts/                # 【新增】契约定义
│   ├─ agent_call.py         # AgentCall Contract v2
│   ├─ agent_result.py       # AgentResult Schema
│   ├─ validator.py          # 契约验证器
│   └─ schemas/              # JSON Schema 定义
│
├─ verification/             # 【新增】验证系统
│   ├─ voting.py             # 多 Agent 投票
│   ├─ adversarial.py        # 对抗验证
│   └─ arbiter.py            # 仲裁逻辑
│
├─ registry/                 # capability registry + agent registry
├─ lease/                    # lease manager + resource registry + health
│
├─ agents/                   # specialist agents
│   ├─ browser/
│   ├─ mobile/
│   ├─ container/
│   └─ vm/
│
├─ drivers/                  # webdriver/cdp/appium/k8s/ssh adapters
├─ storage/                  # postgres + s3 + vector store adapters
│   ├─ postgres.py
│   ├─ s3.py
│   ├─ redis.py
│   └─ vector.py             # 【新增】向量存储适配器
│
├─ observability/            # otel setup + exporters + dashboards
└─ sdk/                      # python/js client
```

---

## 13. 里程碑（Roadmap）

### Milestone 0（1~2 周）：契约与骨架
- 完成三份契约：AgentCall / Registry / Lease
- 搭建 Orchestrator 状态机（最小闭环）
- OTel 基础接入 + Evidence Store

### Milestone 1（2~4 周）：浏览器域闭环（优先）
- BrowserAgent（WebDriver）+ 基础证据（截图/DOM/HAR/action_log）
- fanout 并行（多浏览器 context）
- Critic 验收与换资源重试

### Milestone 2（4~6 周）：容器与数据处理
- ContainerAgent（K8s Job）执行脚本任务
- 证据/工件回收与索引
- 基础配额/租户隔离

### Milestone 3（6~10 周）：手机域（Appium 标准）
- MobileAgent（Android 真机/模拟器）
- UI-tree/截图/录屏证据
- iOS 预留字段与驱动接口（XCUITest/WDA）

### Milestone 4（10~14 周）：多 VM/桌面
- VMDesktopAgent（SSH/RDP）
- 录屏与动作回放

### Milestone 5：AutoGLM 融合（不破坏标准）
- AutoGLM 作为“意图→动作计划”的上层生成器
- 底层执行仍走 Appium/WebDriver，保留回放与审计一致性

---

## 14. 关键决策记录（ADR 建议）

建议建立 `docs/adr/`：
- ADR-001：Agent-as-a-Service 与禁止直连工具
- ADR-002：WebDriver/Appium 作为标准执行入口
- ADR-003：Lease 作为强制执行门禁
- ADR-004：证据与回放一等公民
- ADR-005：OpenAPI 外部 + gRPC 内部

---

## 15. 附录：命名规范与版本化

### 15.1 Agent 命名
- `general.planner`
- `general.executor`
- `general.critic`
- `browser.webdriver`
- `browser.chrome_devtools_mcp`
- `mobile.appium`
- `container.k8s_job`
- `vm.desktop`

### 15.2 Schema 命名
- `browser.navigate_and_extract.v1`
- `mobile.open_app_and_tap.v1`
- `container.run_job_and_collect.v1`

### 15.3 协议兼容
- 输出 schema 只增不改；必要时升版本（v2）
- Agent endpoint 可多版本共存，Router 依据 schema 选择

---

## 16. 交付物清单（v1）

- [ ] OpenAPI：Task/Session API（含 timeline/evidence/replay）
- [ ] gRPC：AgentGateway、CapabilityRegistry、LeaseManager
- [ ] Orchestrator：Step 状态机 + DAG Scheduler + Router + Policy
- [ ] Specialist Agents：BrowserAgent(WebDriver)、MobileAgent(Appium, Android)、ContainerAgent(K8s)
- [ ] Evidence：S3 存储 + Postgres 索引
- [ ] Observability：OTel Trace/Log/Metric + 基础仪表盘
- [ ] **Memory System**：向量存储 + 记忆检索 + 经验沉淀
- [ ] **Intent Negotiation**：NegotiatorAgent + 意图解析 + 协商对话
- [ ] **Adversarial Verification**：VotingAgent + 多路验证 + 冲突仲裁

---

## 17. 长期记忆系统（Execution Memory）

> 让系统"越用越聪明"：通过记忆存储、检索和更新，积累执行经验，优化后续任务规划与执行。

### 17.1 记忆存储架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Memory Store                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │ Vector Store  │  │   Postgres    │  │    Redis      │       │
│  │ (Embeddings)  │  │ (Structured)  │  │ (Hot Cache)   │       │
│  │               │  │               │  │               │       │
│  │ - 语义检索    │  │ - 元数据索引  │  │ - 热点缓存    │       │
│  │ - 相似匹配    │  │ - 关系查询    │  │ - 会话状态    │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### 17.2 记忆类型

#### A. Task Pattern Cache（任务模式缓存）

存储成功执行的任务规划模板，用于相似任务的快速规划。

```python
TaskPattern = {
    'id': str,
    'task_signature': str,           # 任务签名（用于语义匹配）
    'embedding': List[float],        # 向量表示
    'successful_plan': {
        'steps': List[Step],         # 成功的步骤规划
        'dag_structure': str,        # DAG 结构描述
    },
    'execution_stats': {
        'success_count': int,
        'avg_duration_ms': int,
        'avg_cost_usd': float,
    },
    'applicable_contexts': List[str], # 适用场景
    'created_at': datetime,
    'last_used_at': datetime,
}
```

#### B. Failure Knowledge Base（失败知识库）

记录失败原因与解决方案的映射关系。

```python
FailureKnowledge = {
    'id': str,
    'failure_signature': str,        # 失败特征签名
    'embedding': List[float],
    'failure_pattern': {
        'error_type': str,           # 错误类型
        'error_message': str,        # 错误信息
        'context_features': Dict,    # 上下文特征
    },
    'solutions': [
        {
            'strategy': str,         # 解决策略
            'success_rate': float,   # 成功率
            'steps': List[str],      # 解决步骤
        }
    ],
    'root_causes': List[str],        # 根因分析
}
```

#### C. Site Profile（站点/应用画像）

存储目标网站或应用的结构特征和历史交互经验。

```python
SiteProfile = {
    'id': str,
    'domain': str,                   # 域名/包名
    'type': 'web' | 'mobile_app',
    'structure': {
        'key_pages': Dict,           # 关键页面结构
        'navigation_paths': List,    # 导航路径
        'element_patterns': Dict,    # 元素定位模式
    },
    'anti_automation': {
        'captcha_types': List[str],  # 验证码类型
        'rate_limits': Dict,         # 频率限制
        'detection_methods': List,   # 检测方法
    },
    'selector_evolution': [          # Selector 演化历史
        {
            'element': str,
            'old_selector': str,
            'new_selector': str,
            'changed_at': datetime,
        }
    ],
    'last_crawled_at': datetime,
}
```

#### D. Agent Performance（智能体性能统计）

记录各 Agent 的执行表现，用于路由优化。

```python
AgentPerformance = {
    'agent_id': str,
    'capability': str,
    'metrics': {
        'total_calls': int,
        'success_rate': float,
        'avg_latency_ms': float,
        'avg_cost_usd': float,
        'p99_latency_ms': float,
    },
    'by_task_type': Dict[str, Dict], # 按任务类型细分
    'recent_failures': List[Dict],   # 近期失败记录
    'updated_at': datetime,
}
```

### 17.3 记忆检索机制

```python
class MemoryRetriever:
    def __init__(self, vector_store, postgres, redis):
        self.vector_store = vector_store
        self.postgres = postgres
        self.redis = redis

    async def retrieve_context(self, task: Dict) -> MemoryContext:
        """为任务检索相关记忆上下文"""
        task_embedding = await self.embed(task['intent'])

        # 并行检索
        similar_patterns, site_profile, known_failures = await asyncio.gather(
            self.find_similar_patterns(task_embedding, top_k=3),
            self.get_site_profile(task.get('target_domain')),
            self.find_relevant_failures(task_embedding, top_k=5),
        )

        return MemoryContext(
            similar_tasks=similar_patterns,
            site_profile=site_profile,
            known_issues=known_failures,
        )

    async def find_similar_patterns(self, embedding, top_k=3) -> List[TaskPattern]:
        """向量相似度检索"""
        # 先查 Redis 缓存
        cache_key = f"pattern:{hash(tuple(embedding[:10]))}"
        cached = await self.redis.get(cache_key)
        if cached:
            return cached

        # 向量检索
        results = await self.vector_store.search(
            collection='task_patterns',
            vector=embedding,
            top_k=top_k,
            threshold=0.85,
        )

        # 缓存结果
        await self.redis.setex(cache_key, 300, results)
        return results
```

### 17.4 记忆更新策略

```python
class MemoryUpdater:
    async def update_after_execution(self, task: Dict, result: Dict):
        """执行后更新记忆"""
        if result['status'] == 'success':
            await self.update_success_pattern(task, result)
            await self.update_agent_performance(task, result, success=True)
        else:
            await self.update_failure_knowledge(task, result)
            await self.update_agent_performance(task, result, success=False)

        # 更新站点画像
        if 'site_observations' in result:
            await self.update_site_profile(result['site_observations'])

    async def update_success_pattern(self, task: Dict, result: Dict):
        """更新成功模式"""
        pattern_id = await self.find_or_create_pattern(task)
        await self.postgres.execute("""
            UPDATE task_patterns
            SET success_count = success_count + 1,
                avg_duration_ms = (avg_duration_ms * success_count + $1) / (success_count + 1),
                last_used_at = NOW()
            WHERE id = $2
        """, result['metrics']['latency_ms'], pattern_id)
```

### 17.5 记忆配置

```yaml
memory:
  enabled: true

  vector_store:
    type: "pgvector"  # pgvector / milvus / pinecone
    embedding_model: "text-embedding-3-small"
    embedding_dim: 1536

  retrieval:
    similarity_threshold: 0.85
    max_results: 5
    cache_ttl_seconds: 300

  retention:
    task_patterns_days: 180
    failure_knowledge_days: 365
    site_profiles_days: 90

  update:
    batch_size: 100
    async_update: true
```

---

## 18. 子智能体调用规范（AgentCall Contract v2）

> 统一的 Agent 调用契约，确保每次调用都是可追踪、可验证、可复现的。

### 18.1 AgentCall 完整规范

```python
AgentCall = {
    # ==================== 核心意图 ====================
    'intent': str,                        # 自然语言意图描述
    'intent_structured': {                # 结构化意图（可选）
        'action': str,                    # 动作类型
        'target': str,                    # 目标对象
        'parameters': Dict[str, Any],     # 参数
    },

    # ==================== 返回要求 ====================
    'return_spec': {
        'schema_id': str,                 # 输出 Schema 标识
        'required_fields': List[str],     # 必须返回的字段
        'optional_fields': List[str],     # 可选字段
        'format': 'json' | 'text' | 'binary',
    },

    # ==================== 验收标准 ====================
    'success_criteria': {
        'conditions': List[str],          # 成功条件列表（AND 关系）
        'timeout_ms': int,                # 超时时间
        'max_retries': int,               # 最大重试次数
    },
    'evidence_required': List[str],       # 必须证据类型

    # ==================== 上下文（核心增强）====================
    'context': {
        # 上游结果（DAG 调度器自动注入）
        'upstream_results': Dict[str, Any],

        # 记忆上下文（Memory System 自动注入）
        'memory_context': {
            'similar_tasks': List[Dict],  # 相似任务的历史执行
            'site_profile': Dict,         # 目标站点画像
            'known_issues': List[Dict],   # 已知问题和解决方案
            'recommended_strategies': List[str],
        },

        # 用户补充上下文
        'user_context': str,

        # 会话上下文
        'session_context': {
            'previous_steps': List[str],  # 已执行步骤摘要
            'accumulated_data': Dict,     # 累积数据
        },
    },

    # ==================== 约束条件 ====================
    'constraints': {
        # 域约束
        'allowed_domains': List[str],
        'forbidden_domains': List[str],
        'allowed_actions': List[str],
        'forbidden_actions': List[str],   # ['purchase', 'delete', 'send_message']

        # 预算约束
        'time_budget_ms': int,
        'cost_budget_usd': float,
        'token_budget': int,

        # 安全约束
        'secrets_scope': str,             # 可访问的密钥域
        'risk_level': 'low' | 'medium' | 'high',
        'requires_human_approval': bool,

        # 其他标志
        'flags': {
            'no_purchase': bool,
            'no_external_api': bool,
            'dry_run': bool,              # 模拟执行
        },
    },

    # ==================== 执行控制 ====================
    'execution': {
        'lease_id': str,                  # 资源租约 ID（执行型必需）

        'model_profile': {
            'preferred_models': List[str],
            'fallback_models': List[str],
            'max_cost_per_call_usd': float,
            'temperature': float,
        },

        'retry_policy': {
            'max_retries': int,
            'backoff_strategy': 'exponential' | 'linear' | 'fixed',
            'initial_delay_ms': int,
            'max_delay_ms': int,
        },

        'resource_hints': {
            'prefer_resource_ids': List[str],
            'avoid_resource_ids': List[str],
        },
    },

    # ==================== 验证配置（新增）====================
    'verification': {
        'mode': 'single' | 'voting' | 'adversarial',
        'config': {
            # Voting 模式
            'num_voters': int,
            'voter_models': List[str],
            'consensus_strategy': 'majority' | 'unanimous' | 'weighted',

            # Adversarial 模式
            'challenger_enabled': bool,
            'arbiter_model': str,
        },
    },

    # ==================== 追踪信息 ====================
    'tracing': {
        'task_id': str,
        'step_id': str,
        'call_id': str,
        'parent_call_id': str,            # 父调用（嵌套调用场景）
        'trace_id': str,                  # OTel Trace ID
        'span_id': str,                   # OTel Span ID
    },

    # ==================== 元数据 ====================
    'metadata': {
        'created_at': datetime,
        'caller_agent': str,
        'priority': 'low' | 'normal' | 'high' | 'critical',
        'tags': List[str],
    },
}
```

### 18.2 AgentResult 返回规范

```python
AgentResult = {
    # ==================== 状态 ====================
    'status': 'success' | 'failed' | 'partial' | 'needs_user' | 'needs_retry',
    'status_detail': str,                 # 状态详情

    # ==================== 输出 ====================
    'outputs': Dict[str, Any],            # 按 return_spec 返回

    # ==================== 证据 ====================
    'evidence': {
        'screenshots': List[str],         # S3 URIs
        'videos': List[str],
        'dom_snapshots': List[str],
        'network_har': str,
        'action_log': List[Dict],         # 动作日志
        'console_log': List[str],
        'file_artifacts': List[str],
    },
    'replay_uri': str,                    # 回放入口

    # ==================== 指标 ====================
    'metrics': {
        'latency_ms': int,
        'cost_usd': float,
        'tokens_used': int,
        'retries': int,
        'resources_used': List[str],
    },

    # ==================== 记忆更新建议（新增）====================
    'memory_update': {
        'lessons_learned': List[str],     # 经验教训
        'site_observations': Dict,        # 站点观察
        'selector_updates': List[Dict],   # Selector 更新
        'pattern_refinement': Dict,       # 模式优化建议
    },

    # ==================== 错误信息 ====================
    'error': {
        'code': str,
        'message': str,
        'recoverable': bool,
        'suggested_action': str,
    } | None,

    # ==================== 追踪 ====================
    'tracing': {
        'call_id': str,
        'trace_id': str,
        'span_id': str,
        'duration_ms': int,
    },
}
```

### 18.3 契约验证

```python
class ContractValidator:
    """AgentCall 契约验证器"""

    def validate_call(self, call: AgentCall) -> ValidationResult:
        errors = []

        # 必填字段检查
        if not call.get('intent'):
            errors.append("缺少 intent 字段")
        if not call.get('return_spec'):
            errors.append("缺少 return_spec 字段")
        if not call.get('tracing', {}).get('task_id'):
            errors.append("缺少 tracing.task_id")

        # 执行型必须有 lease
        if self.is_execution_call(call) and not call.get('execution', {}).get('lease_id'):
            errors.append("执行型调用必须提供 lease_id")

        # 高风险操作必须有验证配置
        if call.get('constraints', {}).get('risk_level') == 'high':
            if call.get('verification', {}).get('mode') == 'single':
                errors.append("高风险操作建议启用 voting 或 adversarial 验证")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def validate_result(self, call: AgentCall, result: AgentResult) -> ValidationResult:
        errors = []

        # 检查必须字段是否返回
        required_fields = call.get('return_spec', {}).get('required_fields', [])
        outputs = result.get('outputs', {})
        for field in required_fields:
            if field not in outputs:
                errors.append(f"缺少必须输出字段: {field}")

        # 检查必须证据是否提供
        required_evidence = call.get('evidence_required', [])
        evidence = result.get('evidence', {})
        for ev_type in required_evidence:
            if not evidence.get(ev_type):
                errors.append(f"缺少必须证据: {ev_type}")

        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

---

## 19. 意图协商机制（Intent Negotiation）

> 在任务执行前，通过 NegotiatorAgent 澄清用户意图，减少歧义，提高执行成功率。

### 19.1 协商流程

```
用户输入（可能模糊）
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                  NegotiatorAgent                     │
├──────────────────────────────────────────────────────┤
│  1. 意图解析                                          │
│     - 提取核心目标                                    │
│     - 识别实体（人/物/地点/时间）                     │
│     - 检测隐含需求                                    │
│     - 标记歧义点                                      │
│                                                      │
│  2. 上下文补全                                        │
│     - 查询用户历史偏好（Memory）                      │
│     - 推断缺失参数                                    │
│     - 检索相似任务规划                                │
│                                                      │
│  3. 约束推导                                          │
│     - 风险评估                                        │
│     - 权限检查                                        │
│     - 资源预估                                        │
│     - 成本预估                                        │
│                                                      │
│  4. 协商对话（按需）                                  │
│     - 生成澄清问题                                    │
│     - 提供选项                                        │
│     - 确认理解                                        │
└──────────────────────────────────────────────────────┘
       │
       ▼
结构化 Task Spec（明确）
```

### 19.2 NegotiationSession Schema

```python
NegotiationSession = {
    'session_id': str,
    'created_at': datetime,

    # === 原始输入 ===
    'raw_input': {
        'text': str,                      # 原始用户输入
        'attachments': List[str],         # 附件（截图/文件）
        'context': str,                   # 对话上下文
    },

    # === 意图解析结果 ===
    'parsed_intent': {
        'goal': str,                      # 核心目标
        'action_type': str,               # 动作类型
        'entities': [
            {
                'type': str,              # person/place/time/product/...
                'value': str,
                'confidence': float,
            }
        ],
        'constraints_inferred': Dict,     # 推断的约束
    },

    # === 歧义检测 ===
    'ambiguities': [
        {
            'aspect': str,                # 哪方面不明确
            'description': str,           # 描述
            'options': [                  # 可能的选项
                {
                    'value': str,
                    'description': str,
                    'is_default': bool,
                }
            ],
            'question': str,              # 澄清问题
            'resolved': bool,
            'resolution': str,
        }
    ],

    # === 用户偏好（从 Memory 检索）===
    'user_preferences': {
        'time_preference': str,           # '早班机' / '晚班机'
        'price_sensitivity': 'low' | 'medium' | 'high',
        'risk_tolerance': 'low' | 'medium' | 'high',
        'brand_preferences': List[str],
        'historical_choices': List[Dict],
    },

    # === 资源与成本预估 ===
    'estimation': {
        'estimated_steps': int,
        'estimated_duration_ms': int,
        'estimated_cost_usd': float,
        'required_capabilities': List[str],
        'risk_level': 'low' | 'medium' | 'high',
    },

    # === 协商状态 ===
    'negotiation_state': {
        'rounds': int,                    # 对话轮次
        'questions_asked': List[str],
        'user_responses': List[str],
        'confidence': float,              # 意图理解置信度
    },

    # === 最终输出 ===
    'final_spec': TaskSpec | None,        # 协商后的任务规范
    'status': 'in_progress' | 'confirmed' | 'cancelled',
}
```

### 19.3 协商策略

根据意图理解置信度采取不同策略：

| 置信度 | 策略 | 行为 |
|--------|------|------|
| **> 0.95** | 直接执行 | 跳过确认，直接生成 TaskSpec |
| **0.85 - 0.95** | 快速确认 | 展示理解摘要，请求简单确认 |
| **0.70 - 0.85** | 重点澄清 | 针对 1-2 个关键歧义点提问 |
| **0.50 - 0.70** | 多轮对话 | 系统性澄清多个方面 |
| **< 0.50** | 引导式询问 | 通过结构化问题引导用户描述 |

### 19.4 NegotiatorAgent 实现

```python
class NegotiatorAgent:
    def __init__(self, memory: MemoryStore, llm: LLM):
        self.memory = memory
        self.llm = llm

    async def negotiate(self, raw_input: str, user_id: str) -> NegotiationSession:
        session = NegotiationSession(raw_input=raw_input)

        # 1. 意图解析
        session.parsed_intent = await self.parse_intent(raw_input)

        # 2. 检索用户偏好
        session.user_preferences = await self.memory.get_user_preferences(user_id)

        # 3. 检测歧义
        session.ambiguities = await self.detect_ambiguities(
            session.parsed_intent,
            session.user_preferences,
        )

        # 4. 计算置信度
        session.negotiation_state['confidence'] = self.calculate_confidence(session)

        # 5. 根据置信度决定下一步
        if session.negotiation_state['confidence'] > 0.95:
            session.final_spec = await self.generate_task_spec(session)
            session.status = 'confirmed'
        elif session.negotiation_state['confidence'] > 0.85:
            # 生成确认摘要
            session.confirmation_summary = await self.generate_summary(session)
        else:
            # 生成澄清问题
            session.next_questions = self.prioritize_questions(session.ambiguities)

        return session

    async def respond_to_clarification(
        self,
        session: NegotiationSession,
        user_response: str
    ) -> NegotiationSession:
        """处理用户对澄清问题的回答"""
        # 更新歧义解决状态
        session = await self.update_ambiguities(session, user_response)

        # 重新计算置信度
        session.negotiation_state['confidence'] = self.calculate_confidence(session)
        session.negotiation_state['rounds'] += 1

        # 检查是否可以结束协商
        if session.negotiation_state['confidence'] > 0.85:
            session.final_spec = await self.generate_task_spec(session)
            session.status = 'confirmed'

        return session
```

### 19.5 协商配置

```yaml
negotiation:
  enabled: true

  confidence_thresholds:
    auto_execute: 0.95
    quick_confirm: 0.85
    focused_clarify: 0.70
    multi_round: 0.50

  limits:
    max_rounds: 5
    max_questions_per_round: 3
    session_timeout_seconds: 600

  default_preferences:
    assume_lowest_risk: true
    prefer_confirmation: true
```

---

## 20. 多 Agent 投票与对抗验证（Adversarial Verification）

> 对于高风险任务，通过多个 Agent 独立执行并投票，或通过挑战者-仲裁者模式验证结果，提高可靠性。

### 20.1 验证模式

#### A. Single 模式（默认）
单个 Agent 执行，CriticAgent 验收。适用于低风险任务。

#### B. Voting 模式（多数投票）

```
                     高风险 Step
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     ┌─────────┐    ┌─────────┐    ┌─────────┐
     │ Agent A │    │ Agent B │    │ Agent C │
     │(GPT-4)  │    │(Claude) │    │(DeepSeek)│
     └────┬────┘    └────┬────┘    └────┬────┘
          │               │               │
          ▼               ▼               ▼
     Result A        Result B        Result C
          │               │               │
          └───────────────┼───────────────┘
                          ▼
                 ┌─────────────────┐
                 │  VotingAgent    │
                 ├─────────────────┤
                 │ - 结果对比      │
                 │ - 一致性检查    │
                 │ - 冲突检测      │
                 │ - 置信度评估    │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ Final Decision  │
                 └─────────────────┘
```

#### C. Adversarial 模式（对抗验证）

```
                     高风险 Step
                          │
                          ▼
                 ┌─────────────────┐
                 │  ExecutorAgent  │  ← 执行任务
                 └────────┬────────┘
                          │ Result
                          ▼
                 ┌─────────────────┐
                 │ ChallengerAgent │  ← 专门找问题
                 ├─────────────────┤
                 │ - 验证数据准确性│
                 │ - 检查逻辑漏洞  │
                 │ - 模拟边界情况  │
                 │ - 质疑假设前提  │
                 └────────┬────────┘
                          │ Challenges
                          ▼
                 ┌─────────────────┐
                 │  ArbiterAgent   │  ← 最终裁决
                 ├─────────────────┤
                 │ - 评估挑战有效性│
                 │ - 综合判断      │
                 │ - 生成最终结论  │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ Final Decision  │
                 └─────────────────┘
```

### 20.2 VerificationConfig

```python
VerificationConfig = {
    'mode': 'single' | 'voting' | 'adversarial',

    # === Voting 模式配置 ===
    'voting': {
        'num_voters': 3,                  # 投票 Agent 数量
        'voter_configs': [
            {
                'model': 'gpt-4',
                'weight': 1.0,            # 投票权重
                'timeout_ms': 30000,
            },
            {
                'model': 'claude-3-opus',
                'weight': 1.0,
                'timeout_ms': 30000,
            },
            {
                'model': 'deepseek-v3',
                'weight': 0.8,
                'timeout_ms': 30000,
            },
        ],
        'consensus_strategy': 'majority' | 'unanimous' | 'weighted',
        'min_agreement_ratio': 0.67,      # 最小一致率
        'tie_breaker': 'highest_confidence' | 'first_response' | 'arbiter',
    },

    # === Adversarial 模式配置 ===
    'adversarial': {
        'executor_config': {
            'model': 'gpt-4',
            'timeout_ms': 60000,
        },
        'challenger_config': {
            'model': 'claude-3-opus',      # 建议用不同模型
            'challenge_aspects': [
                'data_accuracy',
                'logic_consistency',
                'edge_cases',
                'assumption_validity',
            ],
            'max_challenges': 5,
            'timeout_ms': 30000,
        },
        'arbiter_config': {
            'model': 'gpt-4-turbo',
            'timeout_ms': 30000,
        },
    },

    # === 触发条件 ===
    'triggers': {
        'risk_levels': ['high'],          # 风险等级触发
        'action_types': [                 # 动作类型触发
            'purchase',
            'transfer',
            'delete',
            'send_message',
            'sign_contract',
        ],
        'amount_threshold_usd': 100.0,    # 金额阈值
        'custom_rules': [                 # 自定义规则
            {
                'condition': 'domain in ["bank.com", "payment.com"]',
                'mode': 'adversarial',
            },
        ],
    },
}
```

### 20.3 VotingResult Schema

```python
VotingResult = {
    'verification_id': str,
    'mode': 'voting' | 'adversarial',
    'created_at': datetime,

    # === 个体结果 ===
    'individual_results': [
        {
            'voter_id': str,
            'model': str,
            'result': Dict[str, Any],
            'confidence': float,
            'reasoning': str,
            'execution_time_ms': int,
            'cost_usd': float,
        }
    ],

    # === 共识分析 ===
    'consensus': {
        'reached': bool,
        'agreement_ratio': float,         # 一致率
        'final_result': Dict[str, Any],
        'confidence': float,
        'decision_method': str,           # 'unanimous' / 'majority' / 'arbiter'
    },

    # === 冲突分析 ===
    'conflicts': [
        {
            'field': str,                 # 冲突字段
            'values': List[Any],          # 各方结果
            'voters': List[str],          # 持各观点的 voter
            'resolution': str,            # 解决方式
            'resolved_value': Any,
        }
    ],

    # === 对抗验证特有（Adversarial 模式）===
    'challenges': [
        {
            'aspect': str,
            'challenge': str,
            'executor_response': str,
            'arbiter_verdict': 'valid' | 'invalid' | 'partial',
            'impact': 'none' | 'minor' | 'major',
        }
    ] | None,

    # === 最终决策 ===
    'decision': 'accept' | 'reject' | 'needs_human' | 'needs_retry',
    'decision_reasoning': str,
}
```

### 20.4 VotingAgent 实现

```python
class VotingAgent:
    def __init__(self, config: VerificationConfig):
        self.config = config

    async def verify_with_voting(self, step: Step, call: AgentCall) -> VotingResult:
        """多 Agent 投票验证"""
        voting_config = self.config['voting']

        # 并行执行所有 voter
        tasks = [
            self.execute_voter(voter_config, step, call)
            for voter_config in voting_config['voter_configs']
        ]
        individual_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤失败的结果
        valid_results = [r for r in individual_results if not isinstance(r, Exception)]

        # 分析共识
        consensus = self.analyze_consensus(valid_results, voting_config)

        # 检测冲突
        conflicts = self.detect_conflicts(valid_results)

        # 生成最终决策
        decision = self.make_decision(consensus, conflicts, voting_config)

        return VotingResult(
            individual_results=valid_results,
            consensus=consensus,
            conflicts=conflicts,
            decision=decision,
        )

    def analyze_consensus(self, results: List[Dict], config: Dict) -> Dict:
        """分析投票共识"""
        if not results:
            return {'reached': False, 'agreement_ratio': 0}

        # 提取关键输出字段进行对比
        key_fields = self.extract_key_fields(results)

        # 计算一致率
        agreement_counts = {}
        for field, values in key_fields.items():
            most_common = max(set(values), key=values.count)
            agreement_counts[field] = values.count(most_common) / len(values)

        overall_agreement = sum(agreement_counts.values()) / len(agreement_counts)

        # 根据策略判断是否达成共识
        strategy = config['consensus_strategy']
        min_ratio = config['min_agreement_ratio']

        if strategy == 'unanimous':
            reached = overall_agreement == 1.0
        elif strategy == 'majority':
            reached = overall_agreement >= min_ratio
        else:  # weighted
            reached = self.calculate_weighted_agreement(results, config) >= min_ratio

        return {
            'reached': reached,
            'agreement_ratio': overall_agreement,
            'final_result': self.merge_results(results) if reached else None,
            'confidence': overall_agreement,
        }

    async def verify_with_adversarial(self, step: Step, call: AgentCall) -> VotingResult:
        """对抗验证"""
        adversarial_config = self.config['adversarial']

        # 1. Executor 执行
        executor_result = await self.execute_with_config(
            adversarial_config['executor_config'], step, call
        )

        # 2. Challenger 挑战
        challenges = await self.generate_challenges(
            adversarial_config['challenger_config'],
            step, call, executor_result
        )

        # 3. Arbiter 裁决
        arbiter_verdict = await self.arbitrate(
            adversarial_config['arbiter_config'],
            executor_result, challenges
        )

        return VotingResult(
            mode='adversarial',
            individual_results=[executor_result],
            challenges=challenges,
            decision=arbiter_verdict['decision'],
            decision_reasoning=arbiter_verdict['reasoning'],
        )
```

### 20.5 验证配置示例

```yaml
verification:
  # 默认模式
  default_mode: "single"

  # 高风险自动升级
  auto_escalation:
    enabled: true
    risk_high_mode: "voting"
    financial_mode: "adversarial"
    amount_threshold_usd: 100

  # Voting 配置
  voting:
    default_voters: 3
    default_models: ["gpt-4", "claude-3-opus", "deepseek-v3"]
    consensus_strategy: "majority"
    min_agreement_ratio: 0.67
    timeout_per_voter_ms: 30000

  # Adversarial 配置
  adversarial:
    challenger_model: "claude-3-opus"
    arbiter_model: "gpt-4-turbo"
    max_challenges: 5

  # 成本控制
  cost_limits:
    max_verification_cost_usd: 1.0
    fallback_to_single_on_budget: true
```

---

## 21. 整合后的执行流程

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           完整执行流程 (v2)                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  用户输入                                                                    │
│      │                                                                       │
│      ▼                                                                       │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  NegotiatorAgent (意图协商)                                    ║          │
│  ║  - 意图解析 → 歧义检测 → 用户偏好查询 → 协商对话               ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│      │                                                                       │
│      ▼ TaskSpec                                                              │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  PlannerAgent                                                  ║          │
│  ║  - 生成 Steps with deps[] (DAG 结构)                          ║          │
│  ║  - 注入 Memory Context (相似任务、站点画像)                    ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│      │                                                                       │
│      ▼ DAG[Steps]                                                            │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  DAG Scheduler (层级化 Kahn 算法)                              ║          │
│  ║  - 拓扑排序 → [[L0], [L1], ..., [Ln]]                         ║          │
│  ║  - 层内并行、层间串行                                          ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│      │                                                                       │
│      ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Layer-by-Layer Execution                                           │    │
│  │  ┌───────────────────────────────────────────────────────────────┐ │    │
│  │  │ Level N: [Step1, Step2, Step3] ─────────────┐                 │ │    │
│  │  │      │                                       │                 │ │    │
│  │  │      ▼ (并行)                                ▼                 │ │    │
│  │  │  ╔════════════════════════════════════════════════════════╗  │ │    │
│  │  │  ║  AgentCall (Contract v2)                               ║  │ │    │
│  │  │  ║  + context.upstream_results (自动注入)                  ║  │ │    │
│  │  │  ║  + context.memory_context (自动注入)                    ║  │ │    │
│  │  │  ╚════════════════════════════════════════════════════════╝  │ │    │
│  │  │      │                                                        │ │    │
│  │  │      ▼                                                        │ │    │
│  │  │  ╔════════════════════════════════════════════════════════╗  │ │    │
│  │  │  ║  Verification (按 risk_level 选择模式)                  ║  │ │    │
│  │  │  ║  - Single: 直接执行                                     ║  │ │    │
│  │  │  ║  - Voting: 多 Agent 投票                                ║  │ │    │
│  │  │  ║  - Adversarial: 执行→挑战→仲裁                         ║  │ │    │
│  │  │  ╚════════════════════════════════════════════════════════╝  │ │    │
│  │  │      │                                                        │ │    │
│  │  │      ▼                                                        │ │    │
│  │  │  ╔════════════════════════════════════════════════════════╗  │ │    │
│  │  │  ║  CriticAgent (验收)                                     ║  │ │    │
│  │  │  ║  → accept / retry / switch_resource / replan            ║  │ │    │
│  │  │  ╚════════════════════════════════════════════════════════╝  │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  │                          │                                          │    │
│  │                          ▼                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────┐ │    │
│  │  │ Level N+1: 等待 Level N 完成后执行                            │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                          │                                                   │
│                          ▼                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  Memory Update                                                 ║          │
│  ║  - 存储成功模式 (Task Pattern)                                 ║          │
│  ║  - 记录失败教训 (Failure Knowledge)                            ║          │
│  ║  - 更新站点画像 (Site Profile)                                 ║          │
│  ║  - 统计 Agent 性能 (Agent Performance)                         ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│                          │                                                   │
│                          ▼                                                   │
│                    Task Result                                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 22. 技术评审与改进建议

> 本章及后续章节为对 v1 方案的技术评审结果与改进建议，重点关注：复用性、调用延迟、内存/资源回收、安全性、轻量化设计。

### 22.1 整体架构评价

#### 优点

1. **分层清晰** - Control Plane / Agent Plane / Resource Plane / Execution Plane 四层划分合理，职责边界明确
2. **Agent-as-a-Service 理念先进** - 所有能力封装为 Agent，禁止上层直连工具，这是正确的抽象层次
3. **契约优先设计** - 强制声明 Intent/Return Spec/Success Criteria/Evidence Required，为可审计和可验证奠定基础

#### 识别的问题与改进方向

| 问题 | 影响 | 改进方向 |
|------|------|----------|
| 层级过多导致延迟累积 | 完整请求可能经过 6+ 层调用 | 引入 Fast Path，根据复杂度动态选择路径 |
| Control Plane 单点风险 | Orchestrator/Router/Scheduler 高度集中 | 需要高可用设计 |
| CriticAgent 职责过重 | 同时负责验收、纠偏、资源切换、重规划 | 拆分为 ValidatorAgent + RecoveryAgent |
| 契约过于庞大 | AgentCall 包含 15+ 顶级字段，学习成本高 | 提供分层契约模板 |
| DAG 缺少动态重构能力 | replan 时无法修改执行中的 DAG | 增加 DAGMutator 组件 |

### 22.2 评分总结

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 架构完整性 | 4.5 | 分层清晰，覆盖全面 |
| 技术选型 | 4.5 | 标准优先原则执行到位 |
| 可扩展性 | 4.0 | 插件化设计良好，动态 DAG 需加强 |
| 可靠性设计 | 4.0 | 验证机制完善，故障恢复需细化 |
| 安全性设计 | 3.5 | 框架有，实现细节需补充 |
| 可操作性 | 3.5 | 契约复杂度高，需要简化版本 |

---

## 23. 内存回收机制

> 完整的内存生命周期管理，支持分层存储、自动迁移、任务级作用域和压力响应。

### 23.1 分层内存模型

```python
class MemoryHierarchy:
    """
    三级内存模型：Hot → Warm → Cold
    自动根据访问频率和时效性在层级间迁移
    """

    # L1: Hot Memory (Redis) - 毫秒级访问
    # - 当前活跃任务上下文
    # - 最近 N 分钟的执行状态
    # - 高频访问的 Pattern Cache

    # L2: Warm Memory (Postgres + pgvector) - 10ms 级访问
    # - 任务历史和结果
    # - Site Profile
    # - Agent Performance 统计

    # L3: Cold Memory (S3/对象存储) - 100ms 级访问
    # - 历史证据归档
    # - 过期 Pattern 归档
    # - 审计日志归档
```

### 23.2 内存条目元数据

```python
@dataclass
class MemoryEntry:
    """内存条目元数据"""
    id: str
    type: MemoryType  # TASK_CONTEXT | PATTERN | EVIDENCE | PROFILE
    created_at: datetime
    last_accessed_at: datetime
    access_count: int
    size_bytes: int
    ttl_seconds: int
    tier: MemoryTier  # HOT | WARM | COLD

    # 引用计数（用于安全回收）
    ref_count: int = 0

    # 所属任务（用于级联回收）
    task_id: Optional[str] = None

    # 是否可淘汰（某些关键数据需保护）
    evictable: bool = True

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.created_at + timedelta(seconds=self.ttl_seconds)

    def should_demote(self) -> bool:
        """判断是否应降级到下一层"""
        idle_seconds = (datetime.utcnow() - self.last_accessed_at).total_seconds()
        if self.tier == MemoryTier.HOT:
            return idle_seconds > 300  # 5分钟未访问降级
        elif self.tier == MemoryTier.WARM:
            return idle_seconds > 86400  # 1天未访问降级
        return False
```

### 23.3 内存生命周期管理器

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

    async def _evict(self, entry: MemoryEntry):
        """淘汰单个条目"""
        if entry.ref_count > 0:
            raise MemoryError(f"Cannot evict entry {entry.id} with ref_count={entry.ref_count}")

        await self._delete_from_tier(entry.tier, entry.id)
        await self.registry.unregister(entry.id)
        await self.event_bus.emit(MemoryEvictedEvent(entry))

    async def _demote(self, entry: MemoryEntry):
        """降级到下一层"""
        value = await self._read_from_tier(entry.tier, entry.id)
        next_tier = self._get_next_tier(entry.tier)

        await self._store_to_tier(next_tier, entry.id, value)
        await self._delete_from_tier(entry.tier, entry.id)

        entry.tier = next_tier
        await self.registry.update(entry)

    async def _promote(self, entry: MemoryEntry):
        """晋升到上一层"""
        value = await self._read_from_tier(entry.tier, entry.id)
        prev_tier = self._get_prev_tier(entry.tier)

        await self._store_to_tier(prev_tier, entry.id, value)
        entry.tier = prev_tier
        await self.registry.update(entry)
```

### 23.4 任务级联回收

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


# 使用示例
async def execute_task(task: Task):
    async with TaskMemoryScope(task.id, memory_manager) as scope:
        await scope.store('context', task.context, ttl_seconds=3600)
        await scope.store('intermediate_results', results, ttl_seconds=1800)
        result = await do_work()
    # <- 作用域结束时自动调用 cleanup()
```

### 23.5 内存压力响应

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
            await self.memory_manager.gc()
            self.config.per_task_memory_limit *= 0.8

        elif level == 'critical':
            await self._force_demote_inactive()
            await self.scheduler.pause_new_tasks()
            await self.alert('memory_critical', usage=usage)

        elif level == 'emergency':
            await self.memory_manager._evict_lru(target_free_ratio=0.3)
            await self.scheduler.cancel_non_critical_tasks()
            await self.alert('memory_emergency', usage=usage, severity='critical')
```

### 23.6 内存配置

```yaml
memory:
  # 层级配置
  tiers:
    hot:
      backend: redis
      max_size_mb: 512
      default_ttl_seconds: 300
    warm:
      backend: postgres
      max_size_mb: 2048
      default_ttl_seconds: 86400
    cold:
      backend: s3
      max_size_mb: unlimited
      default_ttl_seconds: 2592000  # 30 days

  # 迁移策略
  migration:
    demote_after_idle_seconds:
      hot_to_warm: 300
      warm_to_cold: 86400
    promote_after_access_count: 10

  # GC 配置
  gc:
    interval_seconds: 60
    pressure_threshold: 0.8
    lru_eviction_ratio: 0.2

  # 保留策略
  retention:
    task_context_days: 7
    evidence_days: 90
    audit_logs_days: 365
```

---

## 24. 资源回收机制

> 完整的资源生命周期管理，包括状态机、租约管理、自动清理和弹性伸缩。

### 24.1 资源生命周期状态机

```python
class ResourceState(Enum):
    """资源状态"""
    INITIALIZING = 'initializing'
    IDLE = 'idle'
    LEASED = 'leased'
    RELEASING = 'releasing'
    UNHEALTHY = 'unhealthy'
    TERMINATED = 'terminated'


class ResourceLifecycle:
    """
    资源生命周期状态机

    INITIALIZING → IDLE ⇄ LEASED
                    ↓       ↓
                RELEASING ← ┘
                    ↓
               TERMINATED

    Any State → UNHEALTHY → RELEASING → TERMINATED
    """

    TRANSITIONS = {
        ResourceState.INITIALIZING: [ResourceState.IDLE, ResourceState.UNHEALTHY],
        ResourceState.IDLE: [ResourceState.LEASED, ResourceState.RELEASING, ResourceState.UNHEALTHY],
        ResourceState.LEASED: [ResourceState.IDLE, ResourceState.RELEASING, ResourceState.UNHEALTHY],
        ResourceState.RELEASING: [ResourceState.TERMINATED, ResourceState.UNHEALTHY],
        ResourceState.UNHEALTHY: [ResourceState.RELEASING],
        ResourceState.TERMINATED: [],
    }

    async def transition(self, resource: Resource, to_state: ResourceState) -> bool:
        if to_state not in self.TRANSITIONS[resource.state]:
            raise InvalidTransitionError(
                f"Cannot transition from {resource.state} to {to_state}"
            )

        old_state = resource.state
        resource.state = to_state
        resource.state_changed_at = datetime.utcnow()

        await self._on_state_change(resource, old_state, to_state)
        return True

    async def _on_state_change(self, resource: Resource, old: ResourceState, new: ResourceState):
        if new == ResourceState.RELEASING:
            asyncio.create_task(self._cleanup_resource(resource))
        elif new == ResourceState.UNHEALTHY:
            asyncio.create_task(self._handle_unhealthy(resource))

        await self.event_bus.emit(ResourceStateChangedEvent(resource, old, new))
```

### 24.2 租约管理

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


class LeaseManager:
    """租约管理器"""

    async def acquire(self, request: LeaseRequest) -> Lease:
        resource = await self.resource_registry.find_available(
            capabilities=request.capabilities,
            labels=request.label_selector,
        )

        if not resource:
            raise ResourceUnavailableError("No available resource")

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

        async with self.resource_registry.lock(resource.id):
            if resource.state != ResourceState.IDLE:
                raise ResourceUnavailableError("Resource no longer available")

            await self.resource_lifecycle.transition(resource, ResourceState.LEASED)
            resource.current_lease_id = lease.id
            self.leases[lease.id] = lease

        asyncio.create_task(self._monitor_lease(lease))
        return lease

    async def release(self, lease_id: str, cleanup: bool = True):
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
        lease = self.leases.get(lease_id)
        if not lease or lease.state != LeaseState.ACTIVE:
            raise LeaseError("Lease not found or not active")

        if lease.renewal_count >= lease.max_renewals:
            raise LeaseError("Max renewals exceeded")

        extension = extension_seconds or self.config.default_extension_seconds
        new_expiry = lease.expires_at + timedelta(seconds=extension)

        total_duration = (new_expiry - lease.acquired_at).total_seconds()
        if total_duration > lease.max_duration_seconds:
            raise LeaseError("Would exceed max lease duration")

        lease.expires_at = new_expiry
        lease.renewal_count += 1
        return lease

    async def _monitor_lease(self, lease: Lease):
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

    async def gc(self) -> LeaseGCStats:
        stats = LeaseGCStats()

        for lease_id, lease in list(self.leases.items()):
            if lease.state in [LeaseState.RELEASED, LeaseState.EXPIRED]:
                del self.leases[lease_id]
                stats.cleaned_count += 1

            if not await self.task_registry.exists(lease.task_id):
                await self.release(lease_id)
                stats.orphaned_count += 1

        return stats
```

### 24.3 资源清理器

```python
class ResourceCleaner:
    """资源清理器 - 不同类型资源的清理策略"""

    def __init__(self):
        self.cleaners = {
            ResourceType.BROWSER: BrowserCleaner(),
            ResourceType.MOBILE: MobileCleaner(),
            ResourceType.CONTAINER: ContainerCleaner(),
            ResourceType.VM: VMCleaner(),
        }

    async def cleanup(self, resource: Resource) -> CleanupResult:
        cleaner = self.cleaners.get(resource.type)
        if not cleaner:
            raise ValueError(f"No cleaner for resource type: {resource.type}")
        return await cleaner.cleanup(resource)


class BrowserCleaner:
    """浏览器资源清理"""

    async def cleanup(self, resource: BrowserResource) -> CleanupResult:
        result = CleanupResult(resource_id=resource.id)

        try:
            driver = await self._get_driver(resource)

            # 1. 关闭所有标签页
            windows = await driver.get_window_handles()
            for window in windows[1:]:
                await driver.switch_to.window(window)
                await driver.close()

            # 2. 清除浏览器状态
            await driver.delete_all_cookies()
            await driver.execute_script("window.localStorage.clear();")
            await driver.execute_script("window.sessionStorage.clear();")

            # 3. 清除缓存
            if hasattr(driver, 'execute_cdp_cmd'):
                await driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                await driver.execute_cdp_cmd('Network.clearBrowserCookies', {})

            # 4. 导航到空白页
            await driver.get('about:blank')

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)
            await self.resource_lifecycle.transition(resource, ResourceState.UNHEALTHY)

        return result


class ContainerCleaner:
    """容器资源清理"""

    async def cleanup(self, resource: ContainerResource) -> CleanupResult:
        result = CleanupResult(resource_id=resource.id)

        try:
            k8s = self.k8s_client

            # 1. 停止运行中的进程
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['pkill', '-9', '-f', '.'])

            # 2. 清理临时文件
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['rm', '-rf', '/tmp/*', '/var/tmp/*'])

            # 3. 清理工作目录
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['rm', '-rf', f'{resource.work_dir}/*'])

            # 4. 重置网络连接
            await k8s.exec_in_pod(resource.pod_name, resource.namespace,
                ['ss', '-K'])

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)
            await self._recreate_container(resource)

        return result
```

### 24.4 资源池管理

```python
class ResourcePool:
    """资源池管理"""

    def __init__(self, config: PoolConfig):
        self.config = config
        self.pools: Dict[ResourceType, TypedPool] = {}
        self._init_pools()

    async def warm_up(self):
        """预热资源池"""
        tasks = [pool.ensure_min_size() for pool in self.pools.values()]
        await asyncio.gather(*tasks)

    async def acquire(self, resource_type: ResourceType, timeout_ms: int = 5000) -> Resource:
        pool = self.pools.get(resource_type)
        if not pool:
            raise ValueError(f"Unknown resource type: {resource_type}")

        try:
            return await asyncio.wait_for(pool.acquire(), timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            if pool.can_scale_up():
                return await pool.scale_up_one()
            raise ResourceUnavailableError("Pool exhausted")

    async def release(self, resource: Resource):
        pool = self.pools.get(resource.type)
        if pool:
            await self.cleaner.cleanup(resource)
            await pool.release(resource)

    async def maintain(self):
        """资源池维护循环"""
        while True:
            for pool in self.pools.values():
                # 健康检查
                unhealthy = await pool.health_check()
                for resource in unhealthy:
                    await pool.remove(resource)

                # 弹性伸缩
                if pool.utilization > pool.scale_up_threshold:
                    await pool.scale_up()
                elif pool.utilization < pool.scale_down_threshold:
                    await pool.scale_down()

                # 清理过期空闲资源
                expired = await pool.get_expired_idle()
                for resource in expired:
                    await pool.remove(resource)

            await asyncio.sleep(self.config.maintain_interval_seconds)


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
        if len(self.all_resources) == 0:
            return 0
        return len(self.in_use) / len(self.all_resources)

    async def acquire(self) -> Resource:
        resource = await self.idle.get()
        self.in_use.add(resource.id)
        return resource

    async def release(self, resource: Resource):
        self.in_use.discard(resource.id)
        await self.idle.put(resource)

    async def scale_up(self, count: int = 1):
        async with self._lock:
            for _ in range(count):
                if len(self.all_resources) >= self.max_size:
                    break
                resource = await self._create_resource()
                self.all_resources[resource.id] = resource
                await self.idle.put(resource)

    async def scale_down(self, count: int = 1):
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

---

## 25. 安全性增强

> 五层安全架构，覆盖边界安全、身份访问、执行沙箱、数据安全和运行时防护。

### 25.1 多层安全架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           安全架构分层                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: 边界安全 (Perimeter Security)                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • API Gateway 认证/授权    • Rate Limiting / DDoS 防护              │   │
│  │ • TLS 终止 / mTLS          • WAF 规则                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Layer 2: 身份与访问控制 (Identity & Access)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • 多租户隔离 (Tenant Isolation)    • RBAC 权限模型                   │   │
│  │ • 密钥域隔离 (Secret Scope)        • 审计日志                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Layer 3: 执行沙箱 (Execution Sandbox)                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • 网络隔离 (Network Policy)    • 文件系统隔离                        │   │
│  │ • 进程隔离 (Namespace/Cgroup)  • 资源配额 (CPU/Memory/IO)           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Layer 4: 数据安全 (Data Security)                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • 静态加密 (Encryption at Rest)    • 传输加密 (Encryption in Transit)│   │
│  │ • 数据脱敏 (Data Masking)          • 敏感数据检测 (PII Detection)    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Layer 5: 运行时防护 (Runtime Protection)                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • 行为分析 (Behavior Analysis)    • 异常检测 (Anomaly Detection)     │   │
│  │ • 危险操作拦截                    • 自动熔断                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 25.2 密钥管理

```python
class SecretManager:
    """密钥管理器 - 零信任设计"""

    def __init__(self, vault_client: VaultClient):
        self.vault = vault_client
        self.secret_cache = TTLCache(maxsize=1000, ttl=300)

    async def get_secret(self, secret_path: str, context: SecurityContext) -> SecretValue:
        # 1. 验证访问权限
        if not await self._check_permission(secret_path, context):
            await self._audit_denied_access(secret_path, context)
            raise AccessDeniedError(f"No permission to access {secret_path}")

        # 2. 验证密钥域
        scope = self._extract_scope(secret_path)
        if scope not in context.allowed_scopes:
            raise ScopeViolationError(f"Secret scope {scope} not in allowed scopes")

        # 3. 检查缓存
        cache_key = f"{context.tenant_id}:{secret_path}"
        if cache_key in self.secret_cache:
            return self.secret_cache[cache_key]

        # 4. 从 Vault 获取
        secret = await self.vault.read(path=secret_path, token=context.vault_token)

        # 5. 包装为安全值
        safe_value = SecretValue(
            value=secret.data,
            expires_at=datetime.utcnow() + timedelta(seconds=secret.lease_duration),
            accessor=context.accessor_id,
        )

        self.secret_cache[cache_key] = safe_value
        await self._audit_access(secret_path, context)
        return safe_value

    async def inject_secrets(self, call: AgentCall, context: SecurityContext) -> AgentCall:
        """将密钥注入到 AgentCall（不暴露原始值）"""
        if not call.constraints.secrets_scope:
            return call

        call.execution.secret_refs = {}

        for secret_key in call.required_secrets:
            secret_path = f"{context.tenant_id}/{call.constraints.secrets_scope}/{secret_key}"

            temp_token = await self.vault.create_wrapped_token(
                path=secret_path,
                ttl=call.execution.timeout_ms // 1000 + 60,
                num_uses=1,
            )
            call.execution.secret_refs[secret_key] = temp_token

        return call


class SecretValue:
    """安全的密钥值包装"""

    def __init__(self, value: str, expires_at: datetime, accessor: str):
        self._value = value
        self._expires_at = expires_at
        self._accessor = accessor
        self._accessed = False

    def get(self) -> str:
        if self._accessed:
            raise SecretError("Secret already accessed")
        if datetime.utcnow() > self._expires_at:
            raise SecretError("Secret expired")

        self._accessed = True
        return self._value

    def __str__(self):
        return "***REDACTED***"
```

### 25.3 执行沙箱

```python
class ExecutionSandbox:
    """执行沙箱 - 限制 Agent 的执行环境"""

    async def create_sandbox(self, context: ExecutionContext) -> Sandbox:
        sandbox = Sandbox(id=generate_sandbox_id(), context=context)

        sandbox.network = await self._setup_network_isolation(context)
        sandbox.filesystem = await self._setup_filesystem_isolation(context)
        sandbox.resource_limits = await self._setup_resource_limits(context)
        sandbox.syscall_filter = await self._setup_syscall_filter(context)

        return sandbox

    async def _setup_network_isolation(self, context: ExecutionContext) -> NetworkPolicy:
        return NetworkPolicy(
            allowed_egress_domains=context.constraints.allowed_domains or [],
            blocked_egress_domains=context.constraints.forbidden_domains or [],
            default_egress_policy='deny' if context.risk_level == 'high' else 'allow',
            allowed_ports=[80, 443],
            block_private_ranges=True,
            block_metadata_service=True,
        )

    async def _setup_filesystem_isolation(self, context: ExecutionContext) -> FilesystemPolicy:
        work_dir = f"/sandbox/{context.task_id}"
        return FilesystemPolicy(
            work_dir=work_dir,
            readonly_mounts=['/usr', '/lib', '/lib64'],
            blocked_paths=['/etc/shadow', '/etc/passwd', '/root', '/home'],
            tmp_quota_mb=context.constraints.disk_quota_mb or 100,
            no_symlink_escape=True,
        )

    async def _setup_resource_limits(self, context: ExecutionContext) -> ResourceLimits:
        return ResourceLimits(
            cpu_cores=context.constraints.cpu_cores or 1,
            memory_mb=context.constraints.memory_mb or 512,
            memory_swap_mb=0,
            max_pids=context.constraints.max_pids or 100,
            io_read_bps=10 * 1024 * 1024,
            io_write_bps=10 * 1024 * 1024,
            max_execution_seconds=context.constraints.timeout_ms // 1000,
        )
```

### 25.4 危险操作拦截器

```python
class ActionInterceptor:
    """危险操作拦截器"""

    DANGEROUS_PATTERNS = {
        'url': [
            r'.*\.(exe|msi|dmg|pkg|deb|rpm)$',
            r'.*password.*',
            r'.*admin.*login.*',
        ],
        'form_field': [
            r'credit.?card', r'cvv', r'ssn', r'social.?security',
        ],
        'action': [
            r'delete.*account', r'transfer.*funds',
            r'send.*money', r'confirm.*purchase',
        ],
    }

    async def intercept(self, action: Action, context: ExecutionContext) -> InterceptResult:
        risks = []

        # URL 检查
        if action.url:
            for pattern in self.DANGEROUS_PATTERNS['url']:
                if re.match(pattern, action.url, re.IGNORECASE):
                    risks.append(Risk(type='dangerous_url', pattern=pattern,
                        value=action.url, severity='high'))

        # 表单字段检查
        if action.form_data:
            for field in action.form_data.keys():
                for pattern in self.DANGEROUS_PATTERNS['form_field']:
                    if re.match(pattern, field, re.IGNORECASE):
                        risks.append(Risk(type='sensitive_form_field', pattern=pattern,
                            value=field, severity='medium'))

        # 动作语义检查
        if action.intent:
            for pattern in self.DANGEROUS_PATTERNS['action']:
                if re.match(pattern, action.intent, re.IGNORECASE):
                    risks.append(Risk(type='dangerous_action', pattern=pattern,
                        value=action.intent, severity='critical'))

        # 决策
        if any(r.severity == 'critical' for r in risks):
            return InterceptResult(decision='block', risks=risks, requires_human_approval=True)
        elif any(r.severity == 'high' for r in risks):
            return InterceptResult(decision='escalate', risks=risks,
                escalate_to='adversarial_verification')
        else:
            return InterceptResult(decision='allow', risks=risks)
```

### 25.5 审计系统

```python
class AuditLogger:
    """审计日志系统"""

    async def log(self, event: AuditEvent):
        event.timestamp = datetime.utcnow()
        event.trace_id = get_current_trace_id()
        event.server_id = self.config.server_id
        event.signature = self._sign_event(event)

        await self.buffer.append(event)

        if event.severity in ['critical', 'high']:
            await self.buffer.flush()

    def _sign_event(self, event: AuditEvent) -> str:
        payload = f"{event.timestamp}|{event.type}|{event.actor}|{event.action}|{event.resource}"
        return hmac.new(
            self.config.signing_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()


@dataclass
class AuditEvent:
    """审计事件"""
    type: str
    actor: str
    action: str
    resource: str

    tenant_id: Optional[str] = None
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    outcome: str = 'success'
    details: Dict = field(default_factory=dict)
    risk_level: str = 'low'
    risks_detected: List[str] = field(default_factory=list)

    timestamp: datetime = None
    trace_id: str = None
    server_id: str = None
    signature: str = None
    severity: str = 'info'
```

### 25.6 敏感数据检测与脱敏

```python
class SensitiveDataDetector:
    """敏感数据检测器"""

    PATTERNS = {
        'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        'api_key': r'\b(?:api[_-]?key|apikey|access[_-]?token)["\s:=]+["\']?([a-zA-Z0-9_-]{20,})["\']?\b',
        'password': r'\b(?:password|passwd|pwd)["\s:=]+["\']?([^\s"\']{8,})["\']?\b',
        'private_key': r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',
    }

    def detect(self, text: str) -> List[SensitiveMatch]:
        matches = []
        for data_type, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(SensitiveMatch(
                    type=data_type, start=match.start(),
                    end=match.end(), value=match.group(),
                ))
        return matches

    def mask(self, text: str) -> str:
        matches = self.detect(text)
        for match in sorted(matches, key=lambda m: m.start, reverse=True):
            masked = self._mask_value(match)
            text = text[:match.start] + masked + text[match.end:]
        return text

    def _mask_value(self, match: SensitiveMatch) -> str:
        value = match.value
        if match.type == 'credit_card':
            return '*' * (len(value) - 4) + value[-4:]
        elif match.type == 'email':
            parts = value.split('@')
            return f"{'*' * len(parts[0])}@{parts[1]}"
        elif match.type in ['password', 'api_key', 'private_key']:
            return '***REDACTED***'
        else:
            if len(value) > 6:
                return value[:2] + '*' * (len(value) - 4) + value[-2:]
            return '*' * len(value)
```

---

## 26. 轻量化设计

> 核心功能内置、扩展功能插件化、延迟加载、按需初始化。

### 26.1 轻量级核心

```python
class LightweightCore:
    """轻量级核心 - 最小可运行单元"""

    CORE_COMPONENTS = [
        'orchestrator',
        'lease_manager',
        'memory_manager',
        'audit_logger',
    ]

    OPTIONAL_COMPONENTS = {
        'negotiator': NegotiatorAgent,
        'voting': VotingAgent,
        'memory_system': MemorySystem,
        'web_console': WebConsole,
    }

    def __init__(self, config: Config):
        self.config = config
        self._components: Dict[str, Any] = {}
        self._initialized: Set[str] = set()

    async def init_core(self):
        for name in self.CORE_COMPONENTS:
            await self._init_component(name)

    async def get_component(self, name: str) -> Any:
        if name not in self._initialized:
            await self._init_component(name)
        return self._components.get(name)
```

### 26.2 单文件部署模式

```python
"""
AgentScope Manus Lightweight Core - 可单文件部署

使用方式:
    from manus_core import ManusCore

    core = ManusCore(config)
    await core.start()
    result = await core.execute_task(task)
"""

@dataclass
class CoreConfig:
    """核心配置 - 最小化必要配置"""
    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql://localhost/manus"

    max_concurrent_tasks: int = 100
    default_lease_seconds: int = 300
    memory_pressure_threshold: float = 0.8
    gc_interval_seconds: int = 60

    enable_sandbox: bool = True
    audit_enabled: bool = True

    features: Dict[str, bool] = field(default_factory=lambda: {
        'negotiation': False,
        'voting': False,
        'memory_system': False,
        'speculation': False,
    })


class ManusCore:
    """Manus 轻量级核心"""

    def __init__(self, config: CoreConfig):
        self.config = config
        self.orchestrator = Orchestrator(config)
        self.lease_manager = LeaseManager(config)
        self.memory_manager = MemoryManager(config)
        self.resource_pool = ResourcePool(config)
        self.security = SecurityManager(config)
        self.audit = AuditLogger(config) if config.audit_enabled else NullAuditLogger()

        self._started = False
        self._gc_task: Optional[asyncio.Task] = None

    async def start(self):
        if self._started:
            return

        await self.memory_manager.init()
        await self.resource_pool.warm_up()
        self._gc_task = asyncio.create_task(self._gc_loop())
        self._started = True

    async def stop(self):
        if not self._started:
            return

        if self._gc_task:
            self._gc_task.cancel()

        await self.lease_manager.release_all()
        await self.resource_pool.drain()
        self._started = False

    async def execute_task(self, task: Task) -> TaskResult:
        await self.security.validate_task(task)

        context = ExecutionContext(
            task_id=task.id,
            tenant_id=task.tenant_id,
            security_context=await self.security.create_context(task),
        )

        async with self.memory_manager.task_scope(task.id) as mem_scope:
            result = await self.orchestrator.execute(task, context, mem_scope)

        await self.audit.log(TaskCompletedEvent(task, result))
        return result

    async def _gc_loop(self):
        while True:
            try:
                await self.memory_manager.gc()
                await self.lease_manager.gc()
                await self.resource_pool.maintain()
            except Exception as e:
                logging.error(f"GC error: {e}")

            await asyncio.sleep(self.config.gc_interval_seconds)
```

### 26.3 组件懒加载

```python
class LazyComponent:
    """延迟加载组件装饰器"""

    def __init__(self, factory):
        self.factory = factory
        self._instance = None
        self._lock = asyncio.Lock()

    async def get(self) -> Any:
        if self._instance is None:
            async with self._lock:
                if self._instance is None:
                    self._instance = await self.factory()
        return self._instance


class ComponentRegistry:
    """组件注册表 - 支持懒加载"""

    def __init__(self):
        self._components: Dict[str, LazyComponent] = {}

    def register(self, name: str, factory):
        self._components[name] = LazyComponent(factory)

    async def get(self, name: str) -> Any:
        if name not in self._components:
            raise KeyError(f"Component {name} not registered")
        return await self._components[name].get()


# 使用示例
registry = ComponentRegistry()
registry.register('negotiator', lambda: NegotiatorAgent.create(config))
registry.register('voting', lambda: VotingAgent.create(config))

# 首次获取时才初始化
if task.needs_negotiation:
    negotiator = await registry.get('negotiator')
```

### 26.4 对象池与复用

```python
class ObjectPool:
    """通用对象池"""

    def __init__(self, factory, max_size: int = 100, reset_fn = None):
        self.factory = factory
        self.max_size = max_size
        self.reset_fn = reset_fn or (lambda x: x)
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._created = 0

    async def acquire(self) -> Any:
        try:
            return self._pool.get_nowait()
        except asyncio.QueueEmpty:
            if self._created < self.max_size:
                self._created += 1
                return await self.factory()
            return await self._pool.get()

    async def release(self, obj: Any):
        obj = self.reset_fn(obj)
        try:
            self._pool.put_nowait(obj)
        except asyncio.QueueFull:
            pass


class Pools:
    """全局对象池"""
    agent_calls = ObjectPool(factory=lambda: AgentCall(), max_size=1000,
        reset_fn=lambda c: c.reset())
    results = ObjectPool(factory=lambda: AgentResult(), max_size=1000,
        reset_fn=lambda r: r.reset())
    contexts = ObjectPool(factory=lambda: ExecutionContext(), max_size=500,
        reset_fn=lambda c: c.reset())
```

### 26.5 配置驱动的功能裁剪

```yaml
deployment_mode: lightweight  # lightweight | standard | full

core:
  orchestrator: true
  lease_manager: true
  memory_manager: true
  audit: true

features:
  negotiation:
    enabled: false
  verification:
    voting: false
    adversarial: false
  memory_system:
    enabled: false
    fallback_cache_ttl_seconds: 300
  dag:
    speculation: false
    parallel_levels: true
  web_console:
    enabled: false

resources:
  memory:
    max_entries: 10000
    hot_tier_max_mb: 256
    warm_tier_max_mb: 1024
  pools:
    browser:
      min_idle: 2
      max_size: 20
    mobile:
      min_idle: 1
      max_size: 10
  gc:
    interval_seconds: 120
    aggressive: false
```

### 26.6 轻量化部署架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    轻量化部署架构对比                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Minimal Mode (单进程)                                                      │
│  适用：开发/测试/小规模部署                                                  │
│  依赖：Python 3.9+ | SQLite (或 Postgres) | 可选 Redis                      │
│  内存：~512MB | CPU：1 core | 并发：~10 任务                                │
│                                                                             │
│  Standard Mode (多进程)                                                     │
│  适用：中等规模生产部署                                                      │
│  依赖：Python 3.9+ | Postgres | Redis                                       │
│  内存：~2GB | CPU：4 cores | 并发：~50 任务                                 │
│                                                                             │
│  Full Mode (分布式)                                                         │
│  适用：大规模生产部署                                                        │
│  依赖：K8s | Postgres (HA) | Redis Cluster | S3 | pgvector                  │
│  内存：~8GB+ | CPU：16+ cores | 并发：100+ 任务                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 27. 复用性增强

> 原子能力、行为 Mixin、契约模板、Step 模式库。

### 27.1 Agent 能力原子化拆分

```python
# 原设计：BrowserAgent 包含所有浏览器能力
# 改进：拆分为可组合的原子能力

CapabilityAtom = {
    'browser.navigate': NavigateAtom,
    'browser.interact': InteractAtom,
    'browser.extract': ExtractAtom,
    'browser.evidence': EvidenceAtom,
    'browser.wait': WaitAtom,
}

class BrowserAgent:
    def __init__(self, atoms: List[CapabilityAtom]):
        self.atoms = {a.name: a for a in atoms}

    async def execute(self, call: AgentCall) -> AgentResult:
        required_atoms = self.resolve_atoms(call.intent)
        pipeline = self.build_pipeline(required_atoms)
        return await pipeline.execute()
```

**复用收益**：
- `ExtractAtom` 可被 BrowserAgent 和 MobileAgent 共用
- `EvidenceAtom` 可跨所有 Specialist Agent 复用
- 新增能力只需添加原子，不改动 Agent 框架

### 27.2 通用 Agent 行为 Mixin

```python
class RetryMixin:
    """通用重试逻辑"""
    async def with_retry(self, fn, policy: RetryPolicy):
        for attempt in range(policy.max_retries):
            try:
                return await fn()
            except RetryableError as e:
                await self.backoff(attempt, policy)
        raise MaxRetriesExceeded()


class EvidenceCollectorMixin:
    """通用证据收集"""
    async def collect_evidence(self, types: List[str]) -> Evidence:
        collectors = {
            'screenshot': self.capture_screenshot,
            'dom_snapshot': self.capture_dom,
            'action_log': self.get_action_log,
        }
        return await asyncio.gather(*[
            collectors[t]() for t in types if t in collectors
        ])


class ContextInjectorMixin:
    """通用上下文注入"""
    def inject_context(self, call: AgentCall, memory: MemoryContext):
        call.context.memory_context = memory
        call.context.upstream_results = self.get_upstream_results()
        return call


# Specialist Agent 通过 Mixin 组合能力
class BrowserAgent(RetryMixin, EvidenceCollectorMixin, ContextInjectorMixin):
    pass
```

### 27.3 契约模板化

```python
ContractTemplates = {
    'browser.navigate_and_extract': {
        'base': 'browser.standard',
        'return_spec': {
            'schema_id': 'extraction.v1',
            'required_fields': ['$TARGET_FIELDS'],
        },
        'evidence_required': ['screenshot', 'dom_snapshot'],
        'constraints': {
            'allowed_domains': ['$ALLOWED_DOMAINS'],
        },
    },

    'browser.form_submit': {
        'base': 'browser.standard',
        'verification': {'mode': 'voting'},
        'constraints': {'flags': {'dry_run_first': True}},
    },
}

# 使用时
call = AgentCall.from_template(
    'browser.navigate_and_extract',
    target_fields=['price', 'stock'],
    allowed_domains=['amazon.com'],
    intent='获取商品价格和库存',
)
```

### 27.4 Step 模板库

```python
StepPatternLibrary = {
    'login_flow': {
        'steps': [
            {'id': 'navigate_login', 'capability': 'browser.navigate'},
            {'id': 'fill_credentials', 'capability': 'browser.interact', 'deps': ['navigate_login']},
            {'id': 'submit_and_verify', 'capability': 'browser.interact', 'deps': ['fill_credentials']},
        ],
        'parameterized': ['login_url', 'username_selector', 'password_selector'],
    },

    'search_and_extract': {
        'steps': [
            {'id': 'navigate', 'capability': 'browser.navigate'},
            {'id': 'search', 'capability': 'browser.interact', 'deps': ['navigate']},
            {'id': 'wait_results', 'capability': 'browser.wait', 'deps': ['search']},
            {'id': 'extract', 'capability': 'browser.extract', 'deps': ['wait_results']},
        ],
    },

    'parallel_scrape': {
        'pattern': 'fanout',
        'fanout_step': {'capability': 'browser.extract'},
        'merge_step': {'capability': 'data.merge'},
    },
}

class PlannerAgent:
    async def plan(self, task: TaskSpec) -> List[Step]:
        pattern = self.match_pattern(task)
        if pattern:
            return self.instantiate_pattern(pattern, task.parameters)
        else:
            return await self.generate_custom_plan(task)
```

---

## 28. 调用延迟优化

> Fast Path、并行化、推测执行、异步验证、延迟预算。

### 28.1 层级压缩：引入 Fast Path

```python
class PathSelector:
    """根据任务特征选择执行路径"""

    def select_path(self, task: TaskSpec) -> ExecutionPath:
        complexity = self.assess_complexity(task)

        if complexity == 'trivial':
            return FastPath(
                steps=[DirectExecution(task)],
                skip_negotiation=True,
                skip_planning=True,
            )
        elif complexity == 'simple':
            return StandardPath(
                skip_negotiation=True,
                use_cached_plan=True,
            )
        elif complexity == 'moderate':
            return FullPath(parallel_negotiation_and_memory=True)
        else:
            return FullPath()

    def assess_complexity(self, task: TaskSpec) -> str:
        signals = {
            'has_ambiguity': self.detect_ambiguity(task),
            'multi_step': task.estimated_steps > 3,
            'high_risk': task.risk_level == 'high',
            'new_domain': not self.memory.has_site_profile(task.domain),
            'requires_coordination': task.requires_parallel_agents,
        }

        score = sum(signals.values())
        if score == 0: return 'trivial'
        if score <= 1: return 'simple'
        if score <= 3: return 'moderate'
        return 'complex'
```

### 28.2 并行化关键路径

```python
class OptimizedOrchestrator:
    async def execute_task(self, task: TaskSpec):
        # 阶段 1：并行执行（不等待）
        negotiation_task = asyncio.create_task(
            self.negotiator.negotiate(task) if self.needs_negotiation(task) else None
        )
        memory_task = asyncio.create_task(self.memory.retrieve_context(task))
        resource_task = asyncio.create_task(
            self.lease_manager.pre_acquire(task.estimated_resources)
        )

        # 阶段 2：等待必要结果，开始规划
        memory_context = await memory_task
        negotiated_task = await negotiation_task if negotiation_task else task

        plan = await self.planner.plan(negotiated_task, memory_context)

        # 阶段 3：资源就绪，立即执行
        leases = await resource_task
        return await self.execute_dag(plan, leases)
```

### 28.3 推测执行

```python
class SpeculativeExecutor:
    """在高置信度场景下，提前执行后续步骤"""

    async def execute_with_speculation(self, dag: DAG):
        for level_idx, level in enumerate(dag.levels):
            current_results = await self.execute_level(level)

            if self.all_high_confidence(current_results):
                next_level = dag.levels[level_idx + 1] if level_idx + 1 < len(dag.levels) else None
                if next_level:
                    speculation_task = asyncio.create_task(
                        self.execute_level_speculative(next_level, current_results)
                    )

            verified_results = await self.verify_level(level, current_results)

            if not self.results_match(current_results, verified_results):
                if speculation_task:
                    speculation_task.cancel()
```

### 28.4 CriticAgent 异步化

```python
class OptimisticExecutionMode:
    """乐观执行：先继续后验证"""

    async def execute_step_optimistic(self, step: Step) -> StepResult:
        result = await self.specialist.execute(step)

        if step.risk_level == 'low':
            asyncio.create_task(self.critic.verify_async(step, result))
            return result

        try:
            verified = await asyncio.wait_for(
                self.critic.verify(step, result),
                timeout=step.verification_timeout_ms / 1000
            )
            return verified
        except asyncio.TimeoutError:
            result.status = 'pending_verification'
            return result
```

### 28.5 延迟预算传递

```python
@dataclass
class LatencyBudget:
    """延迟预算，在调用链中传递和扣减"""
    total_ms: int
    remaining_ms: int
    checkpoints: List[Tuple[str, int]]

    def consume(self, stage: str, elapsed_ms: int) -> 'LatencyBudget':
        return LatencyBudget(
            total_ms=self.total_ms,
            remaining_ms=self.remaining_ms - elapsed_ms,
            checkpoints=self.checkpoints + [(stage, elapsed_ms)],
        )

    def can_afford(self, estimated_ms: int) -> bool:
        return self.remaining_ms >= estimated_ms


class LatencyAwareAgent:
    async def execute(self, call: AgentCall) -> AgentResult:
        budget = call.execution.latency_budget

        if budget.remaining_ms < 1000:
            call.execution.model_profile.preferred_models = ['gpt-4o-mini']
            call.evidence_required = ['action_log']

        start = time.monotonic()
        result = await self._execute_internal(call)
        elapsed = (time.monotonic() - start) * 1000

        result.metrics.latency_budget_consumed = elapsed
        result.metrics.latency_budget_remaining = budget.remaining_ms - elapsed
        return result
```

---

## 29. 多 Agent 协商触发机制增强

> 自动触发规则引擎 + 显式调用 API 预留。

### 29.1 自动触发规则引擎

```python
class VerificationTriggerEngine:
    """多 Agent 协商的自动触发规则引擎"""

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> List[TriggerRule]:
        return [
            # 基于风险等级
            TriggerRule(
                name='high_risk_auto_voting',
                condition=lambda ctx: ctx.step.risk_level == 'high',
                action=VerificationMode.VOTING,
                priority=100,
            ),
            TriggerRule(
                name='critical_risk_adversarial',
                condition=lambda ctx: ctx.step.risk_level == 'critical',
                action=VerificationMode.ADVERSARIAL,
                priority=110,
            ),

            # 基于动作类型
            TriggerRule(
                name='financial_action',
                condition=lambda ctx: ctx.step.action_type in ['purchase', 'transfer', 'payment'],
                action=VerificationMode.ADVERSARIAL,
                priority=100,
            ),
            TriggerRule(
                name='destructive_action',
                condition=lambda ctx: ctx.step.action_type in ['delete', 'cancel', 'revoke'],
                action=VerificationMode.VOTING,
                priority=90,
            ),

            # 基于金额阈值
            TriggerRule(
                name='amount_threshold_high',
                condition=lambda ctx: ctx.extract_amount() >= 1000,
                action=VerificationMode.ADVERSARIAL,
                priority=90,
            ),

            # 基于历史表现
            TriggerRule(
                name='low_success_rate_domain',
                condition=lambda ctx: ctx.memory.get_domain_success_rate(ctx.domain) < 0.7,
                action=VerificationMode.VOTING,
                priority=70,
            ),
            TriggerRule(
                name='first_time_domain',
                condition=lambda ctx: not ctx.memory.has_site_profile(ctx.domain),
                action=VerificationMode.VOTING,
                priority=60,
            ),

            # 基于执行上下文
            TriggerRule(
                name='retry_escalation',
                condition=lambda ctx: ctx.retry_count >= 2,
                action=VerificationMode.VOTING,
                priority=70,
            ),
        ]

    def evaluate(self, context: TriggerContext) -> VerificationDecision:
        matched_rules = [rule for rule in self.rules if rule.condition(context)]

        if not matched_rules:
            return VerificationDecision(
                mode=VerificationMode.SINGLE,
                triggered_by=None,
                explicit_override=False,
            )

        top_rule = max(matched_rules, key=lambda r: r.priority)

        return VerificationDecision(
            mode=top_rule.action,
            triggered_by=top_rule.name,
            matched_rules=[r.name for r in matched_rules],
            explicit_override=False,
        )
```

### 29.2 显式调用 API（预留接口）

```python
class VerificationAPI:
    """显式验证调用接口"""

    @staticmethod
    def force_voting(step: Step, config: VotingConfig = None) -> Step:
        """强制该 Step 使用投票验证"""
        step.verification = {
            'mode': 'voting',
            'explicit': True,
            'config': config or VotingConfig.default(),
        }
        return step

    @staticmethod
    def force_adversarial(step: Step, config: AdversarialConfig = None) -> Step:
        """强制该 Step 使用对抗验证"""
        step.verification = {
            'mode': 'adversarial',
            'explicit': True,
            'config': config or AdversarialConfig.default(),
        }
        return step

    @staticmethod
    def force_single(step: Step) -> Step:
        """强制跳过多 Agent 验证（需要审计日志）"""
        step.verification = {
            'mode': 'single',
            'explicit': True,
            'skip_reason_required': True,
        }
        return step

    @staticmethod
    def with_verification(call: AgentCall, mode: str, **kwargs) -> AgentCall:
        """为 AgentCall 添加显式验证配置"""
        call.verification = {
            'mode': mode,
            'explicit': True,
            **kwargs,
        }
        return call

    async def escalate_verification(
        self, step_id: str, reason: str, target_mode: str = 'voting'
    ) -> EscalationResult:
        """运行时升级验证级别"""
        step = await self.get_running_step(step_id)

        if step.status == 'running':
            step.requires_reverification = True
            step.reverification_mode = target_mode
            step.escalation_reason = reason
        elif step.status == 'pending_verification':
            step.verification['mode'] = target_mode
            step.verification['escalated'] = True

        return EscalationResult(
            step_id=step_id,
            original_mode=step.verification.get('mode', 'single'),
            escalated_mode=target_mode,
            reason=reason,
        )
```

### 29.3 验证模式组合

```python
class CompositeVerification:
    """复合验证模式"""

    @staticmethod
    def sequential(modes: List[VerificationMode]) -> VerificationConfig:
        """顺序验证：依次通过所有验证"""
        return VerificationConfig(type='sequential', modes=modes)

    @staticmethod
    def conditional(rules: List[ConditionalRule]) -> VerificationConfig:
        """条件验证：根据前一阶段结果决定后续"""
        return VerificationConfig(type='conditional', rules=rules)

    @staticmethod
    def parallel_consensus(configs: List[VerificationConfig]) -> VerificationConfig:
        """并行验证：多种验证同时进行，综合结果"""
        return VerificationConfig(
            type='parallel_consensus',
            configs=configs,
            consensus_strategy='all_pass',
        )


# 使用示例：高风险金融操作的复合验证
high_risk_financial_verification = CompositeVerification.sequential([
    VerificationConfig(mode='voting', aspect='intent_confirmation', num_voters=3),
    VerificationConfig(mode='adversarial', aspect='data_accuracy',
        challenger_focus=['amount', 'recipient', 'timing']),
    VerificationConfig(mode='human_in_loop', timeout_seconds=300, fallback='reject'),
])
```

### 29.4 触发决策透明性

```python
@dataclass
class VerificationDecision:
    """验证决策的完整记录"""
    mode: VerificationMode
    triggered_by: str
    matched_rules: List[str]
    explicit_override: bool

    explanation: str = None
    trigger_context: Dict = None

    def to_audit_log(self) -> Dict:
        return {
            'timestamp': datetime.utcnow(),
            'mode': self.mode.value,
            'triggered_by': self.triggered_by,
            'matched_rules': self.matched_rules,
            'explicit': self.explicit_override,
            'explanation': self.explanation,
            'context_snapshot': self.trigger_context,
        }


class VerificationOrchestrator:
    async def decide_and_execute(self, step: Step, call: AgentCall) -> VerificationResult:
        # 1. 检查显式声明（优先级最高）
        if call.verification and call.verification.get('explicit'):
            decision = VerificationDecision(
                mode=call.verification['mode'],
                triggered_by='explicit_declaration',
                explicit_override=True,
                explanation=f"显式指定使用 {call.verification['mode']} 模式",
            )
        else:
            # 2. 评估自动触发规则
            context = TriggerContext.from_step_and_call(step, call, self.memory)
            decision = self.trigger_engine.evaluate(context)
            decision.trigger_context = context.to_snapshot()
            decision.explanation = self._generate_explanation(decision)

        # 3. 记录决策（审计）
        await self.audit_log.record(decision.to_audit_log())

        # 4. 执行验证
        return await self._execute_verification(step, call, decision)
```

### 29.5 配置化触发规则

```yaml
verification_rules:
  version: "1.0"

  rules:
    - name: high_risk_auto_voting
      enabled: true
      priority: 100
      condition:
        type: field_match
        field: step.risk_level
        operator: eq
        value: high
      action:
        mode: voting
        config:
          num_voters: 3
          consensus: majority

    - name: amount_threshold_high
      enabled: true
      priority: 90
      condition:
        type: expression
        expr: "context.extract_amount() >= 1000"
      action:
        mode: adversarial

    - name: sensitive_domain
      enabled: true
      priority: 95
      condition:
        type: field_in_list
        field: context.domain
        list: ["bank.com", "payment.com", "crypto.exchange"]
      action:
        mode: adversarial

  explicit_override_allowed:
    - caller: internal_test
    - caller: dry_run_mode
    - condition: "context.user.role == 'admin' and context.has_skip_reason"

  defaults:
    fallback_mode: single
    voting:
      default_num_voters: 3
      default_models: [gpt-4, claude-3-opus, deepseek-v3]
    adversarial:
      default_challenger_model: claude-3-opus
      default_arbiter_model: gpt-4-turbo
```

---

## 30. 改进后的模块依赖图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        模块依赖（轻量化设计）                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                          ┌─────────────────────┐                            │
│                          │     ManusCore       │                            │
│                          │   (入口 + 生命周期)   │                            │
│                          └──────────┬──────────┘                            │
│                                     │                                       │
│            ┌────────────────────────┼────────────────────────┐              │
│            │                        │                        │              │
│            ▼                        ▼                        ▼              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  Orchestrator   │    │  LeaseManager   │    │ MemoryManager   │         │
│  │  (编排调度)      │    │  (租约管理)      │    │ (内存管理)       │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                   │
│           │                      ▼                      ▼                   │
│           │             ┌─────────────────┐    ┌─────────────────┐         │
│           │             │  ResourcePool   │    │   GCManager     │         │
│           │             │  (资源池)        │    │  (垃圾回收)      │         │
│           │             └─────────────────┘    └─────────────────┘         │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    Agent Execution Layer                         │       │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │       │
│  │  │ BrowserAgent│  │ MobileAgent │  │ContainerAgent│              │       │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │       │
│  │         └────────────────┼────────────────┘                      │       │
│  │                          ▼                                       │       │
│  │               ┌─────────────────────┐                            │       │
│  │               │  SecurityManager    │                            │       │
│  │               │  (沙箱 + 拦截)       │                            │       │
│  │               └─────────────────────┘                            │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -   │
│                        可选组件（延迟加载）                                   │
│  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -   │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ Negotiator  │  │  Voting     │  │MemorySystem │  │ WebConsole  │       │
│  │ (意图协商)   │  │ (多Agent验证)│  │ (长期记忆)   │  │ (控制台)    │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│        ▲                ▲                ▲                ▲                 │
│        └────────────────┴────────────────┴────────────────┘                 │
│                    通过 ComponentRegistry 按需加载                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 31. 改进总结

| 维度 | 改进要点 |
|------|----------|
| **内存回收** | 三级内存模型 + 任务级作用域 + 引用计数 + 压力响应 + 层级自动迁移 |
| **资源回收** | 状态机生命周期 + 租约自动续租/过期 + 类型化清理器 + 资源池弹性伸缩 |
| **安全性** | 五层安全架构 + 密钥零信任 + 执行沙箱 + 危险操作拦截 + 完整审计 |
| **轻量化** | 核心/可选分离 + 延迟加载 + 对象池复用 + 配置驱动裁剪 + 多部署模式 |
| **复用性** | 原子能力 + 行为 Mixin + 契约模板 + Step 模式库 |
| **延迟优化** | Fast Path + 并行化 + 推测执行 + 异步验证 + 延迟预算 |
| **验证触发** | 规则引擎自动触发 + 显式 API 预留 + 配置化热更新 + 决策透明可审计 |
