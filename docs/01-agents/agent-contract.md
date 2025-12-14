# Agent 调用契约（AgentCall Contract v2）

> 统一的 Agent 调用契约，确保每次调用都是可追踪、可验证、可复现的。

## AgentCall 完整规范

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

    # ==================== 上下文 ====================
    'context': {
        # 上游结果（DAG 调度器自动注入）
        'upstream_results': Dict[str, Any],

        # 记忆上下文（Memory System 自动注入）
        'memory_context': {
            'similar_tasks': List[Dict],      # 相似任务的历史执行
            'site_profile': Dict,             # 目标站点画像
            'known_issues': List[Dict],       # 已知问题和解决方案
            'recommended_strategies': List[str],
        },

        # 用户补充上下文
        'user_context': str,

        # 会话上下文
        'session_context': {
            'previous_steps': List[str],      # 已执行步骤摘要
            'accumulated_data': Dict,         # 累积数据
        },
    },

    # ==================== 约束条件 ====================
    'constraints': {
        # 域约束
        'allowed_domains': List[str],
        'forbidden_domains': List[str],
        'allowed_actions': List[str],
        'forbidden_actions': List[str],       # ['purchase', 'delete', 'send_message']

        # 预算约束
        'time_budget_ms': int,
        'cost_budget_usd': float,
        'token_budget': int,

        # 安全约束
        'secrets_scope': str,                 # 可访问的密钥域
        'risk_level': 'low' | 'medium' | 'high',
        'requires_human_approval': bool,

        # 其他标志
        'flags': {
            'no_purchase': bool,
            'no_external_api': bool,
            'dry_run': bool,                  # 模拟执行
        },
    },

    # ==================== 执行控制 ====================
    'execution': {
        'lease_id': str,                      # 资源租约 ID（执行型必需）

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

    # ==================== 验证配置 ====================
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
        'parent_call_id': str,                # 父调用（嵌套调用场景）
        'trace_id': str,                      # OTel Trace ID
        'span_id': str,                       # OTel Span ID
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

## AgentResult 返回规范

```python
AgentResult = {
    # ==================== 状态 ====================
    'status': 'success' | 'failed' | 'partial' | 'needs_user' | 'needs_retry',
    'status_detail': str,                     # 状态详情

    # ==================== 输出 ====================
    'outputs': Dict[str, Any],                # 按 return_spec 返回

    # ==================== 证据 ====================
    'evidence': {
        'screenshots': List[str],             # S3 URIs
        'videos': List[str],
        'dom_snapshots': List[str],
        'network_har': str,
        'action_log': List[Dict],             # 动作日志
        'console_log': List[str],
        'file_artifacts': List[str],
    },
    'replay_uri': str,                        # 回放入口

    # ==================== 指标 ====================
    'metrics': {
        'latency_ms': int,
        'cost_usd': float,
        'tokens_used': int,
        'retries': int,
        'resources_used': List[str],
    },

    # ==================== 记忆更新建议 ====================
    'memory_update': {
        'lessons_learned': List[str],         # 经验教训
        'site_observations': Dict,            # 站点观察
        'selector_updates': List[Dict],       # Selector 更新
        'pattern_refinement': Dict,           # 模式优化建议
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

## 契约验证

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

## 使用示例

### 浏览器导航并提取数据

```python
call = AgentCall(
    intent="导航到商品页面并提取价格信息",
    intent_structured={
        'action': 'navigate_and_extract',
        'target': 'https://example.com/product/123',
        'parameters': {'fields': ['price', 'title', 'stock']},
    },
    return_spec={
        'schema_id': 'browser.extract.v1',
        'required_fields': ['price', 'title'],
        'optional_fields': ['stock'],
        'format': 'json',
    },
    success_criteria={
        'conditions': ['price is not null', 'price > 0'],
        'timeout_ms': 30000,
        'max_retries': 3,
    },
    evidence_required=['screenshot', 'dom_snapshot'],
    constraints={
        'allowed_domains': ['example.com'],
        'flags': {'no_purchase': True},
    },
    execution={
        'lease_id': 'lease-xxx-yyy',
        'model_profile': {
            'preferred_models': ['gpt-4o-mini'],
            'temperature': 0.3,
        },
    },
    tracing={
        'task_id': 'task-123',
        'step_id': 'step-1',
        'call_id': 'call-abc',
    },
)
```

## 证据类型枚举

| 类型 | 说明 | 产出 Agent |
|------|------|-----------|
| `screenshot` | 页面截图 | Browser, Mobile, VM |
| `video` | 录屏 | Browser, Mobile, VM |
| `dom_snapshot` | DOM 快照 | Browser |
| `network_har` | 网络请求日志 | Browser |
| `ui_tree` | 手机控件树 | Mobile |
| `console_log` | 控制台日志 | Browser, Container |
| `action_log` | 动作执行日志 | All |
| `file_artifact` | 文件工件 | Container, VM |
