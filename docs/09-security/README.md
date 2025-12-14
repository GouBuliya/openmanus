# 安全治理

## 概述

五层安全架构，覆盖边界安全、身份访问、执行沙箱、数据安全和运行时防护。

## 安全架构分层

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

## 密钥管理

### 最小权限原则

- Secret 通过 `vault://` 引用
- 按 `secrets_scope` 下发给必要的 Specialist Agent
- 上层 Agent 不直接接触明文凭据（只拿到状态证明/引用）

### SecretManager

```python
class SecretManager:
    """密钥管理器 - 零信任设计"""

    async def get_secret(self, secret_path: str, context: SecurityContext) -> SecretValue:
        # 1. 验证访问权限
        if not await self._check_permission(secret_path, context):
            await self._audit_denied_access(secret_path, context)
            raise AccessDeniedError(f"No permission to access {secret_path}")

        # 2. 验证密钥域
        scope = self._extract_scope(secret_path)
        if scope not in context.allowed_scopes:
            raise ScopeViolationError(f"Secret scope {scope} not in allowed scopes")

        # 3. 从 Vault 获取
        secret = await self.vault.read(path=secret_path, token=context.vault_token)

        return SecretValue(value=secret.data, expires_at=..., accessor=...)
```

## 网络与文件系统策略

### 网络策略

```python
NetworkPolicy = {
    'allowed_egress_domains': List[str],  # 白名单
    'blocked_egress_domains': List[str],  # 黑名单
    'default_egress_policy': 'deny' | 'allow',
    'allowed_ports': [80, 443],
    'block_private_ranges': True,
    'block_metadata_service': True,
}
```

### 文件系统策略

- 可读写路径限制
- 挂载点隔离
- 上传/下载路径分离

## 高风险操作门禁

| 操作类型 | 门禁策略 |
|---------|---------|
| `no_purchase=true` | 禁止任何购买操作 |
| 购买/发送 | 需要"二次确认"或"人审"（NEEDS_USER） |
| 删除/撤销 | 需要明确确认 |

## 执行沙箱

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
```

## 配置参考

```yaml
security:
  # 边界安全
  api_gateway:
    rate_limit:
      requests_per_minute: 100
      burst: 20
    tls:
      min_version: "TLS1.2"
      mtls_enabled: true

  # 密钥管理
  secrets:
    vault_url: "https://vault.example.com"
    cache_ttl_seconds: 300
    audit_all_access: true

  # 执行沙箱
  sandbox:
    default_network_policy: "deny"
    allowed_ports: [80, 443]
    block_private_ranges: true
    resource_limits:
      cpu: "1"
      memory: "1Gi"

  # 审计
  audit:
    enabled: true
    retention_days: 365
```

## 相关文档

- [Agent 契约](../01-agents/agent-contract.md)
- [资源管理](../03-resources/README.md)
