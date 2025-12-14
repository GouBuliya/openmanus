# 资源管理系统

## 概述

资源管理系统负责统一管理浏览器、容器、VM、手机等执行资源，提供：
- **资源注册与发现**
- **租约化访问控制**
- **资源池管理与弹性伸缩**
- **健康检查与自动清理**

## 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                      Resource Plane                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │    Resource     │  │     Lease       │  │    Resource     │ │
│  │    Registry     │  │    Manager      │  │      Pool       │ │
│  │   (资源登记)    │  │   (租约管理)    │  │    (资源池)     │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │           │
│           └────────────────────┼────────────────────┘           │
│                                │                                 │
│                    ┌───────────▼───────────┐                    │
│                    │   Resource Cleaner    │                    │
│                    │     (资源清理器)       │                    │
│                    └───────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## 资源模型

### Resource 字段定义

```python
Resource = {
    'resource_id': str,                    # 唯一标识
    'type': 'browser' | 'mobile' | 'container' | 'vm',
    'capabilities': List[str],             # 支持的能力
    'labels': {                            # K8s 风格标签
        'region': str,
        'os': str,
        'kind': 'real' | 'sim',            # 真机/模拟器
        'browser': str,
        'tenant': str,
    },
    'limits': {
        'concurrency': int,
        'cpu': str,
        'mem': str,
    },
    'health': 'ok' | 'degraded' | 'down',
    'endpoints': {                         # 按类型不同
        'webdriver_url': str,              # browser
        'cdp_url': str,                    # browser
        'appium_url': str,                 # mobile
        'namespace': str,                  # container
        'ssh': str,                        # vm
    },
    'state': ResourceState,
    'current_lease_id': Optional[str],
}
```

### 资源类型

| 类型 | 说明 | Endpoints |
|------|------|-----------|
| `browser` | 浏览器实例 | webdriver_url, cdp_url |
| `mobile` | 手机设备 | appium_url |
| `container` | K8s Pod | namespace, pod_name |
| `vm` | 虚拟机 | ssh, rdp, winrm |

## 调度策略

### 并发控制

| 资源类型 | 并发策略 |
|---------|---------|
| 全局 | **100 running steps**（可配置） |
| 手机真机 | 每台设备 `concurrency=1` |
| 手机模拟器 | 每台 1~2 并发 |
| 浏览器节点 | 按 CPU/内存配置 `max_contexts` |

### 队列优先级

```
interactive > batch
```

### 失败策略

1. **retry** - 幂等/安全操作重试
2. **switch_resource** - 换设备/节点更有效
3. **replan** - Critic 触发重新规划

### 反亲和

同一 Step 的 fanout 副本尽量分配到不同 resource_id。

## 文档索引

| 文档 | 内容 |
|------|------|
| [租约管理](./lease-manager.md) | Lease 生命周期、获取/续租/释放 |
| [资源池](./resource-pool.md) | 资源池设计、弹性伸缩 |
| [资源清理](./resource-cleanup.md) | 不同类型资源的清理策略 |

## 快速参考

### 资源状态机

```
INITIALIZING → IDLE ⇄ LEASED
                ↓       ↓
            RELEASING ← ┘
                ↓
           TERMINATED

Any State → UNHEALTHY → RELEASING → TERMINATED
```

### Lease 字段

```python
Lease = {
    'id': str,
    'resource_id': str,
    'task_id': str,
    'step_id': str,
    'acquired_at': datetime,
    'expires_at': datetime,
    'auto_renew': bool,
    'max_renewals': int,
}
```
