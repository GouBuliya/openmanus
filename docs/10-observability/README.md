# 可观测性

## 概述

全链路 OpenTelemetry 集成，提供 Trace、Log、Metric 三位一体的可观测性。

## OpenTelemetry 集成

### Trace

关键 Span 属性：
- `task_id`, `step_id`, `call_id`
- `agent_name`, `capability`
- `lease_id`, `resource_id`
- `model_name`, `tokens`, `cost_usd`
- `status`, `error_type`

### Logs

结构化日志（JSON），关联 `trace_id`：

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Step completed",
  "trace_id": "abc123",
  "span_id": "def456",
  "task_id": "task_001",
  "step_id": "step_001",
  "duration_ms": 1500
}
```

### Metrics

| 指标 | 类型 | 说明 |
|-----|------|-----|
| `task_total` | Counter | 任务总数 |
| `step_duration_seconds` | Histogram | 步骤耗时 |
| `agent_call_total` | Counter | Agent 调用数 |
| `lease_utilization` | Gauge | 资源利用率 |
| `model_cost_usd_total` | Counter | LLM 成本 |
| `queue_depth` | Gauge | 队列深度 |
| `active_leases` | Gauge | 活跃租约 |
| `browser_pool_available` | Gauge | 可用浏览器数 |

## 事件流

支持 CloudEvents 格式的状态变更事件：

- Step 状态变更
- Lease acquire/release
- Agent 调用结果
- 告警

## 监控栈

```
┌─────────────────────────────────────────────────┐
│                  Grafana                         │
│     (仪表盘、告警、日志查询)                      │
├─────────────────────────────────────────────────┤
│                     │                            │
│    ┌────────────────┼────────────────┐          │
│    ▼                ▼                ▼          │
│ ┌──────┐      ┌──────────┐      ┌──────┐       │
│ │Jaeger│      │Prometheus│      │ Loki │       │
│ │Traces│      │ Metrics  │      │ Logs │       │
│ └──────┘      └──────────┘      └──────┘       │
└─────────────────────────────────────────────────┘
```

## Python 依赖

```toml
opentelemetry-api = "^1.22.0"
opentelemetry-sdk = "^1.22.0"
opentelemetry-instrumentation-fastapi = "^0.43b0"
opentelemetry-instrumentation-grpc = "^0.43b0"
opentelemetry-exporter-jaeger = "^1.22.0"
prometheus-client = "^0.19.0"
```

## 配置

```yaml
observability:
  tracing:
    enabled: true
    exporter: jaeger
    jaeger_endpoint: "http://jaeger:14268/api/traces"
    sample_rate: 1.0

  metrics:
    enabled: true
    exporter: prometheus
    prometheus_port: 9090

  logging:
    enabled: true
    format: json
    level: INFO
    exporter: loki
    loki_url: "http://loki:3100"
```

## 仪表盘设计

### 任务概览

- 任务成功率
- 平均执行时间
- 活跃任务数
- 成本趋势

### 资源监控

- 资源池利用率
- 租约分布
- 健康状态

### Agent 性能

- 调用成功率
- 延迟分布
- Token 使用量
- 成本明细

## 相关文档

- [执行流程](../02-orchestration/execution-flow.md)
- [资源管理](../03-resources/README.md)
