# 契约定义

## 概述

平台采用 **契约优先（Contract-first）** 设计，所有 Agent 调用必须显式声明：
- 做什么（Intent）
- 要返回什么（Return Spec）
- 如何验收（Success Criteria）
- 必须证据（Evidence Required）

## 契约类型

| 类型 | 说明 | 文档 |
|------|------|------|
| **AgentCall** | Agent 调用请求契约 | [agent-call.md](./agent-call.md) |
| **AgentResult** | Agent 返回结果契约 | [agent-result.md](./agent-result.md) |
| **Task API** | 外部 REST API | [api-contracts/openapi.yaml](./api-contracts/openapi.yaml) |
| **gRPC Services** | 内部服务通信 | [api-contracts/grpc/](./api-contracts/grpc/) |

## 外部 API（OpenAPI）

### Task API

```yaml
paths:
  /tasks:
    post:
      summary: 创建任务
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateTaskRequest'

  /tasks/{id}:
    get:
      summary: 查询任务状态

  /tasks/{id}/interrupt:
    post:
      summary: 中断任务

  /tasks/{id}/resume:
    post:
      summary: 恢复任务

  /tasks/{id}/timeline:
    get:
      summary: 获取时间线（steps/events）

  /tasks/{id}/evidence:
    get:
      summary: 获取证据索引（含下载链接）

  /tasks/{id}/replay:
    get:
      summary: 回放入口（按 step 选择）
```

## 内部通信（gRPC）

### AgentGateway

```protobuf
service AgentGateway {
  // 同步调用
  rpc Invoke(AgentCallRequest) returns (AgentCallResponse);

  // 流式调用
  rpc InvokeStream(AgentCallRequest) returns (stream AgentCallResponse);
}
```

### CapabilityRegistry

```protobuf
service CapabilityRegistry {
  // 注册能力
  rpc Register(RegisterCapabilityRequest) returns (RegisterCapabilityResponse);

  // 查询能力
  rpc Query(QueryCapabilityRequest) returns (QueryCapabilityResponse);

  // 健康检查
  rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);
}
```

### LeaseManager

```protobuf
service LeaseManager {
  // 获取租约
  rpc Acquire(AcquireLeaseRequest) returns (AcquireLeaseResponse);

  // 续租
  rpc Renew(RenewLeaseRequest) returns (RenewLeaseResponse);

  // 释放租约
  rpc Release(ReleaseLeaseRequest) returns (ReleaseLeaseResponse);
}
```

## 执行标准

| 领域 | 标准 |
|------|------|
| 浏览器 | **W3C WebDriver（主）**；需要更细能力时：**CDP**（Chromium） |
| 手机 | **Appium（W3C WebDriver 生态）** |
| 容器 | **Kubernetes + OCI** |
| 可观测 | **OpenTelemetry** |
| 事件 | **CloudEvents**（可选） |

## 快速参考

### AgentCall 必填字段

```python
required_fields = [
    'intent',           # 意图描述
    'return_spec',      # 返回规范
    'success_criteria', # 验收标准
    'tracing.task_id',  # 追踪 ID
]
```

### AgentResult 必填字段

```python
required_fields = [
    'status',           # 执行状态
    'outputs',          # 输出数据
    'evidence',         # 证据
    'metrics',          # 指标
    'tracing',          # 追踪信息
]
```

### 证据类型枚举

```python
EvidenceType = [
    'screenshot',       # 截图
    'video',            # 录屏
    'dom_snapshot',     # DOM 快照
    'network_har',      # 网络日志
    'ui_tree',          # UI 控件树
    'console_log',      # 控制台日志
    'action_log',       # 动作日志
    'file_artifact',    # 文件工件
]
```

## 相关文档

- [Agent 调用契约详细规范](../01-agents/agent-contract.md)
- [Step 数据结构](../02-orchestration/dag-scheduler.md)
