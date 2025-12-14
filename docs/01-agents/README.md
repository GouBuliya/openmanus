# Agent 体系设计

## Agent 分类

平台采用两类 Agent 架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                    General Executor Agents                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐│
│  │  Planner    │ │  Executor   │ │   Critic    │ │Coordinator ││
│  │  (规划)     │ │   (调度)    │ │   (验收)    │ │  (仲裁)    ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ AgentCall
┌─────────────────────────────────────────────────────────────────┐
│                   Specialist Executor Agents                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐│
│  │  Browser    │ │   Mobile    │ │  Container  │ │     VM     ││
│  │   Agent     │ │    Agent    │ │    Agent    │ │   Agent    ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## 通用执行 Agent（General Executor Agents）

### PlannerAgent

**职责**：生成/更新任务执行计划

| 字段 | 说明 |
|------|------|
| 输入 | 用户目标、上下文、历史步骤 |
| 输出 | Steps（计划），每步显式声明能力与返回要求 |

```python
# PlannerAgent 输出的 Steps 包含 DAG 依赖关系
steps = [
    Step(id="s1", deps=[], capability="browser.navigate"),
    Step(id="s2", deps=["s1"], capability="browser.extract"),
    Step(id="s3", deps=["s1"], capability="browser.screenshot"),
    Step(id="s4", deps=["s2", "s3"], capability="data.merge"),
]
```

### TaskExecutorAgent

**职责**：协调执行，只调用 Specialist Agents（不直连工具）

| 字段 | 说明 |
|------|------|
| 输入 | Step |
| 行为 | 只负责调用 Specialist Agents |
| 输出 | StepResult（汇总） |

### CriticAgent

**职责**：验收执行结果，决定下一步动作

| 字段 | 说明 |
|------|------|
| 输入 | Step、Result、Evidence |
| 输出 | Decision |

**Decision 类型**：
- `accept` - 验收通过
- `retry` - 重试（幂等/安全前提）
- `switch_resource` - 换设备/换节点
- `replan` - 触发重新规划
- `needs_user` - 需要人工介入

### CoordinatorAgent（可选）

**职责**：并行子任务合并、冲突仲裁、投票/一致性检查

## 专用执行 Agent（Specialist Executor Agents）

### BrowserAgent

执行浏览器自动化任务。

```
BrowserAgent
├── 执行标准：CDP/MCP 优先，WebDriver 补充
├── 二级路由：
│   ├── ChromeDevtoolsMcpAgent（CDP 能力）
│   └── WebDriverAgent（标准 WebDriver）
└── 证据产出：screenshot, dom_snapshot, network_har, action_log
```

### MobileAgent

执行移动端自动化任务。

```
MobileAgent
├── 执行标准：Appium（W3C WebDriver 生态）
├── Android：UiAutomator2
├── iOS 预留：XCUITest（WDA 管理）
├── 可选叠加：AutoGLM（意图→动作计划）
└── 证据产出：screenshot, ui_tree, video, action_log
```

### ContainerAgent

执行容器化脚本任务。

```
ContainerAgent
├── 执行标准：Kubernetes Job/Pod
├── 工件产出：file_artifacts
├── 日志采集：container_logs
└── 证据产出：stdout, stderr, artifacts
```

### VMDesktopAgent

执行虚拟机/桌面自动化任务。

```
VMDesktopAgent
├── 连接方式：SSH/RDP/WinRM/VNC
├── 桌面自动化：可运行 PyAutoGUI 等工具
└── 证据产出：video, screenshot, command_log
```

### DataOpsAgent（可选）

执行数据处理任务（低风险，可无 Lease）。

```
DataOpsAgent
├── 结构化抽取
├── 文件处理
├── 格式转换
└── 证据产出：file_artifacts, transform_log
```

## Agent 对外契约（强制）

每次 Agent 调用必须包含以下字段：

```python
AgentCall = {
    'intent': str,                    # 要做什么
    'return_spec': {                  # 要返回什么
        'schema_id': str,
        'required_fields': List[str],
    },
    'success_criteria': str,          # 如何验收
    'evidence_required': List[str],   # 必须产出的证据类型
    'constraints': Dict,              # 约束条件
    'model_profile': Dict,            # 模型选择策略
    'lease_id': str,                  # 执行型必需
}
```

> **强制规则**：任何 Specialist Agent 必须返回 `outputs + evidence + metrics + replay_uri`

## 相关文档

- [Agent 调用契约详细规范](./agent-contract.md)
- [通用 Agent 设计](./general-agents.md)
- [专用 Agent 设计](./specialist-agents.md)
