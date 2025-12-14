# 协商配置

## 完整配置

```yaml
negotiation:
  enabled: true

  # ==================== 置信度阈值 ====================
  confidence_thresholds:
    auto_execute: 0.95      # 直接执行
    quick_confirm: 0.85     # 快速确认
    focused_clarify: 0.70   # 重点澄清
    multi_round: 0.50       # 多轮对话

  # ==================== 限制 ====================
  limits:
    max_rounds: 5                    # 最大对话轮次
    max_questions_per_round: 3       # 每轮最大问题数
    session_timeout_seconds: 600     # 会话超时

  # ==================== 默认偏好 ====================
  default_preferences:
    assume_lowest_risk: true         # 默认选择最低风险选项
    prefer_confirmation: true        # 倾向于确认
```

## 配置说明

### 置信度阈值

| 阈值 | 默认值 | 说明 |
|-----|-------|------|
| `auto_execute` | 0.95 | 超过此值直接执行 |
| `quick_confirm` | 0.85 | 超过此值快速确认 |
| `focused_clarify` | 0.70 | 超过此值重点澄清 |
| `multi_round` | 0.50 | 低于此值引导式询问 |

### 限制参数

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| `max_rounds` | 5 | 防止无限对话 |
| `max_questions_per_round` | 3 | 每轮问题数限制 |
| `session_timeout_seconds` | 600 | 会话超时时间 |

## 环境变量

```bash
# 开关
NEGOTIATION_ENABLED=true

# 阈值
NEGOTIATION_AUTO_EXECUTE_THRESHOLD=0.95
NEGOTIATION_QUICK_CONFIRM_THRESHOLD=0.85

# 限制
NEGOTIATION_MAX_ROUNDS=5
NEGOTIATION_SESSION_TIMEOUT=600
```

## 场景配置

### 高精度场景

```yaml
negotiation:
  confidence_thresholds:
    auto_execute: 0.98      # 提高自动执行门槛
    quick_confirm: 0.90

  limits:
    max_rounds: 10          # 允许更多对话
```

### 快速响应场景

```yaml
negotiation:
  confidence_thresholds:
    auto_execute: 0.90      # 降低自动执行门槛
    quick_confirm: 0.80

  limits:
    max_rounds: 3           # 减少对话轮次
    session_timeout_seconds: 120
```

### 高风险场景

```yaml
negotiation:
  confidence_thresholds:
    auto_execute: 0.99      # 几乎不自动执行
    quick_confirm: 0.95

  default_preferences:
    assume_lowest_risk: true
    prefer_confirmation: true
    require_explicit_approval: true  # 需要明确批准
```

## 相关文档

- [意图协商概述](./README.md)
- [NegotiatorAgent](./negotiator-agent.md)
