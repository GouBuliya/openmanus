# 命名规范

## Agent 命名

| 类别 | 命名格式 | 示例 |
|-----|---------|-----|
| 通用 Agent | `general.{role}` | `general.planner`, `general.executor`, `general.critic` |
| 浏览器 Agent | `browser.{driver}` | `browser.webdriver`, `browser.chrome_devtools_mcp` |
| 手机 Agent | `mobile.{driver}` | `mobile.appium` |
| 容器 Agent | `container.{platform}` | `container.k8s_job` |
| VM Agent | `vm.{type}` | `vm.desktop` |

## Schema 命名

格式：`{domain}.{action}.v{version}`

```
browser.navigate_and_extract.v1
mobile.open_app_and_tap.v1
container.run_job_and_collect.v1
```

## 协议兼容性

1. **输出 schema 只增不改**
2. 必要时升版本（v2）
3. Agent endpoint 可多版本共存
4. Router 依据 schema 选择

## 资源命名

| 类型 | 格式 | 示例 |
|-----|------|-----|
| 任务 ID | `task_{uuid}` | `task_abc123def456` |
| 步骤 ID | `step_{序号}` | `step_001` |
| 租约 ID | `lease_{uuid}` | `lease_xyz789` |
| 资源 ID | `{type}_{uuid}` | `browser_abc123` |

## 事件命名

格式：`{domain}.{entity}.{action}`

```
task.step.started
task.step.completed
resource.lease.acquired
resource.lease.released
agent.call.success
agent.call.failed
```

## 配置键命名

使用小写 + 下划线：

```yaml
memory:
  vector_store:
    embedding_model: "text-embedding-3-small"
    embedding_dim: 1536
  retrieval:
    similarity_threshold: 0.85
    max_results: 5
```

## 环境变量命名

格式：`{MODULE}_{SECTION}_{KEY}`

```bash
MEMORY_VECTOR_STORE_TYPE=pgvector
MEMORY_RETRIEVAL_THRESHOLD=0.85
VERIFICATION_AUTO_ESCALATION_ENABLED=true
```
