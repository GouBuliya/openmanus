# 证据与回放系统

## 概述

证据（Evidence）和回放（Replay）是一等公民，所有执行型 Agent 必须返回证据和回放入口。

## 证据类型

```python
EvidenceType = [
    'screenshot',       # 截图
    'video',            # 录屏
    'dom_snapshot',     # DOM 快照
    'network_har',      # 网络日志 (HAR)
    'ui_tree',          # UI 控件树（手机）
    'console_log',      # 控制台日志
    'action_log',       # 动作日志
    'file_artifact',    # 文件工件（下载文件/生成报表）
]
```

## 证据存储

### 存储架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Evidence System                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐         ┌─────────────────┐               │
│  │  Evidence Store │         │ Evidence Index  │               │
│  │    (S3 兼容)    │         │   (Postgres)    │               │
│  │                 │         │                 │               │
│  │ - 截图/录屏     │ ◄─────► │ - 元数据        │               │
│  │ - DOM 快照      │         │ - 权限          │               │
│  │ - HAR 日志      │         │ - task/step 关联│               │
│  │ - 工件文件      │         │ - 下载链接      │               │
│  └─────────────────┘         └─────────────────┘               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### S3 目录结构

```
s3://evidence-bucket/
├── {tenant_id}/
│   ├── {task_id}/
│   │   ├── screenshots/
│   │   │   ├── step_001_before.png
│   │   │   └── step_001_after.png
│   │   ├── videos/
│   │   │   └── step_001.mp4
│   │   ├── dom_snapshots/
│   │   │   └── step_001.html
│   │   └── action_logs/
│   │       └── step_001.json
```

## 回放系统

### 回放 URI

Specialist Agent 必须返回 `replay_uri`：

| 资源类型 | 回放内容 |
|---------|---------|
| 浏览器 | actions + selectors + timings（或脚本引用） |
| 手机 | WebDriver commands / action plan |
| 容器 | 镜像 + 命令 + 参数 + 工件 |
| VM | 命令序列/脚本/会话录屏 |

### ReplayInfo 结构

```python
ReplayInfo = {
    'task_id': str,
    'steps': [
        {
            'step_id': str,
            'replay_url': str,      # 回放入口 URL
            'script_url': str,      # 脚本下载 URL
            'artifacts': List[str], # 关联工件
        }
    ],
}
```

## Evidence 结构

```python
Evidence = {
    'id': str,
    'type': EvidenceType,
    'step_id': str,
    'task_id': str,
    'created_at': datetime,
    'download_url': str,
    'expires_at': datetime,
    'metadata': {
        'size_bytes': int,
        'mime_type': str,
        'checksum': str,
    },
}
```

## API 接口

```yaml
# 获取证据列表
GET /tasks/{taskId}/evidence:
  parameters:
    - type: EvidenceType     # 可选，按类型过滤
    - stepId: string         # 可选，按步骤过滤
  response:
    items: List[Evidence]

# 获取回放信息
GET /tasks/{taskId}/replay:
  parameters:
    - stepId: string         # 可选，指定步骤
  response:
    steps: List[ReplayStep]
```

## 生命周期管理

```yaml
evidence:
  lifecycle:
    - tier: hot
      days: 30
      storage_class: STANDARD
    - tier: warm
      days: 90
      storage_class: STANDARD_IA
    - tier: cold
      days: 365
      storage_class: GLACIER
    - tier: delete
      days: 730
```

## 证据收集 Mixin

```python
class EvidenceCollectorMixin:
    """证据收集能力"""
    async def collect_evidence(self, types: List[str]) -> Evidence:
        evidence = {}
        for type in types:
            evidence[type] = await self._collect(type)
        return evidence
```

## 相关文档

- [Agent 契约](../01-agents/agent-contract.md)
- [契约定义](../11-contracts/README.md)
