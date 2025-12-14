# Step 生命周期

## 状态机

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

## 状态说明

| 状态 | 说明 | 后续状态 |
|------|------|----------|
| `PENDING` | 初始状态，等待调度 | WAITING_DEPS, LEASED |
| `WAITING_DEPS` | 等待上游依赖完成（DAG 调度引入） | LEASED |
| `LEASED` | 已获取资源租约 | RUNNING, LEASE_TIMEOUT |
| `RUNNING` | 正在执行 | SUCCEEDED, FAILED_* |
| `SUCCEEDED` | 执行成功 | - |
| `FAILED_RETRYABLE` | 失败但可重试 | RETRYING |
| `RETRYING` | 重试中 | RUNNING |
| `FAILED_RESOURCE` | 资源故障 | SWITCHING_RESOURCE |
| `SWITCHING_RESOURCE` | 切换资源中 | LEASED |
| `FAILED_FATAL` | 不可恢复的失败 | FAILED |
| `FAILED` | 最终失败 | - |
| `NEEDS_USER` | 需要人工介入 | RUNNING (确认后) |
| `LEASE_TIMEOUT` | 租约超时 | PENDING |

## 状态转换实现

```python
from enum import Enum
from typing import Set


class StepState(Enum):
    PENDING = 'pending'
    WAITING_DEPS = 'waiting_deps'
    LEASED = 'leased'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED_RETRYABLE = 'failed_retryable'
    RETRYING = 'retrying'
    FAILED_RESOURCE = 'failed_resource'
    SWITCHING_RESOURCE = 'switching_resource'
    FAILED_FATAL = 'failed_fatal'
    FAILED = 'failed'
    NEEDS_USER = 'needs_user'
    LEASE_TIMEOUT = 'lease_timeout'


class StepStateMachine:
    """Step 状态机"""

    TRANSITIONS = {
        StepState.PENDING: {
            StepState.WAITING_DEPS,
            StepState.LEASED,
        },
        StepState.WAITING_DEPS: {
            StepState.LEASED,
        },
        StepState.LEASED: {
            StepState.RUNNING,
            StepState.LEASE_TIMEOUT,
        },
        StepState.RUNNING: {
            StepState.SUCCEEDED,
            StepState.FAILED_RETRYABLE,
            StepState.FAILED_RESOURCE,
            StepState.FAILED_FATAL,
            StepState.NEEDS_USER,
        },
        StepState.FAILED_RETRYABLE: {
            StepState.RETRYING,
        },
        StepState.RETRYING: {
            StepState.RUNNING,
        },
        StepState.FAILED_RESOURCE: {
            StepState.SWITCHING_RESOURCE,
        },
        StepState.SWITCHING_RESOURCE: {
            StepState.LEASED,
        },
        StepState.LEASE_TIMEOUT: {
            StepState.PENDING,
        },
        StepState.NEEDS_USER: {
            StepState.RUNNING,
        },
        # 终态
        StepState.SUCCEEDED: set(),
        StepState.FAILED_FATAL: {StepState.FAILED},
        StepState.FAILED: set(),
    }

    def __init__(self, step_id: str, initial_state: StepState = StepState.PENDING):
        self.step_id = step_id
        self.state = initial_state
        self.history = [(initial_state, datetime.utcnow())]

    def can_transition(self, to_state: StepState) -> bool:
        return to_state in self.TRANSITIONS.get(self.state, set())

    def transition(self, to_state: StepState) -> bool:
        if not self.can_transition(to_state):
            raise InvalidTransitionError(
                f"Cannot transition from {self.state} to {to_state}"
            )
        self.state = to_state
        self.history.append((to_state, datetime.utcnow()))
        return True

    def is_terminal(self) -> bool:
        return self.state in {StepState.SUCCEEDED, StepState.FAILED}
```

## Critic 决策逻辑

CriticAgent 根据执行结果决定状态转换：

```python
class CriticDecision(Enum):
    ACCEPT = 'accept'
    RETRY = 'retry'
    SWITCH_RESOURCE = 'switch_resource'
    REPLAN = 'replan'
    NEEDS_USER = 'needs_user'


def decide_next_state(
    decision: CriticDecision,
    current_retries: int,
    max_retries: int,
) -> StepState:
    """根据 Critic 决策确定下一状态"""

    if decision == CriticDecision.ACCEPT:
        return StepState.SUCCEEDED

    elif decision == CriticDecision.RETRY:
        if current_retries < max_retries:
            return StepState.FAILED_RETRYABLE
        else:
            return StepState.FAILED_FATAL

    elif decision == CriticDecision.SWITCH_RESOURCE:
        return StepState.FAILED_RESOURCE

    elif decision == CriticDecision.REPLAN:
        # 触发 PlannerAgent 重新规划
        return StepState.FAILED_FATAL  # 当前步骤标记失败

    elif decision == CriticDecision.NEEDS_USER:
        return StepState.NEEDS_USER

    return StepState.FAILED_FATAL
```

## 失败处理策略

### 重试策略

```python
class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        backoff_strategy: str = 'exponential',
        initial_delay_ms: int = 1000,
        max_delay_ms: int = 30000,
    ):
        self.max_retries = max_retries
        self.backoff_strategy = backoff_strategy
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms

    def get_delay(self, retry_count: int) -> int:
        if self.backoff_strategy == 'exponential':
            delay = self.initial_delay_ms * (2 ** retry_count)
        elif self.backoff_strategy == 'linear':
            delay = self.initial_delay_ms * (retry_count + 1)
        else:  # fixed
            delay = self.initial_delay_ms

        return min(delay, self.max_delay_ms)
```

### 资源切换策略

```python
async def switch_resource(step: Step, failed_resource_id: str) -> Resource:
    """切换到备用资源"""
    # 将失败资源加入黑名单
    step.execution.resource_hints['avoid_resource_ids'].append(failed_resource_id)

    # 重新申请资源
    new_resource = await resource_pool.acquire(
        capabilities=step.capabilities_required,
        label_selector=step.label_selector,
        avoid=step.execution.resource_hints['avoid_resource_ids'],
    )

    return new_resource
```

## 监控指标

```yaml
# Step 状态相关指标
metrics:
  - name: step_state_transitions_total
    type: counter
    labels: [step_id, from_state, to_state]

  - name: step_duration_seconds
    type: histogram
    labels: [step_id, capability, status]

  - name: step_retries_total
    type: counter
    labels: [step_id, capability]

  - name: steps_by_state
    type: gauge
    labels: [state]
```
