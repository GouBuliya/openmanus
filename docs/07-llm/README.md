# 多模型策略

## 概述

模型策略集中化（Model Policy）：模型选择由策略器统一治理；调用可覆盖但需受预算约束。

## 策略器职责

### 1. 默认模型注入

根据 task/step 类型注入默认 `model_profile`：

| 类型 | 策略 | 说明 |
|-----|------|-----|
| **plan** | 高推理 | 质量优先，使用最强模型 |
| **execute** | 低成本/低延迟 | 能完成即可 |
| **critic** | 高精度 | 避免误判完成 |

### 2. 风险升级

根据风险与副作用升级模型与审计：

| 场景 | 策略 |
|-----|------|
| 涉及下单/转账/发送消息 | 强制双重验收（Critic + Policy） |
| 高金额操作 | 升级到最强模型 |
| 破坏性操作 | 需要人工确认 |

### 3. 预算控制

根据预算限制（max_cost/max_latency）做降级/拒绝：

```python
if step.estimated_cost > task.constraints.cost_budget_usd:
    # 降级到更便宜的模型
    step.model_profile = fallback_model_profile

if step.estimated_latency > task.constraints.time_budget_ms:
    # 使用更快的模型
    step.model_profile = fast_model_profile
```

## 子 Agent 模型选择边界

1. 父 Agent 指定 `preferred_models` 与 `policy`
2. 子 Agent 可在列表内选择
3. 子 Agent 必须回传指标用于闭环优化：
   - `metrics.cost_usd`
   - `metrics.latency_ms`
   - `metrics.tokens`

## ModelProfile 结构

```python
ModelProfile = {
    'preferred_models': List[str],    # 首选模型列表
    'fallback_models': List[str],     # 降级模型列表
    'constraints': {
        'max_cost_usd': float,        # 单次调用成本上限
        'max_latency_ms': int,        # 延迟上限
        'max_tokens': int,            # Token 上限
    },
    'policy': {
        'temperature': float,
        'top_p': float,
        'retry_on_error': bool,
    },
}
```

## 模型选择策略

```yaml
model_policy:
  planning:
    models: ["gpt-4o", "claude-3-opus"]
    fallback: ["gpt-4-turbo", "claude-3-sonnet"]
    temperature: 0.7
    max_tokens: 4096

  execution:
    models: ["gpt-4o-mini", "claude-3-haiku"]
    fallback: ["gpt-3.5-turbo"]
    temperature: 0.3
    max_tokens: 2048

  critic:
    models: ["gpt-4o", "claude-3-sonnet"]
    temperature: 0.2
    max_tokens: 1024

  cost_limits:
    per_task_usd: 1.0
    per_step_usd: 0.2
```

## 模型抽象层

```python
# 使用 LiteLLM 统一接口
from litellm import completion

response = await completion(
    model=selected_model,
    messages=messages,
    temperature=profile.policy.temperature,
    max_tokens=profile.constraints.max_tokens,
)
```

## 支持的模型

| 提供商 | 模型 |
|-------|-----|
| OpenAI | gpt-4o, gpt-4-turbo, gpt-3.5-turbo |
| Anthropic | claude-3-opus, claude-3-sonnet, claude-3-haiku |
| Azure OpenAI | 同 OpenAI |
| Google | gemini-pro |
| 本地 | ollama/vllm (Llama/Qwen) |

## 相关文档

- [Agent 契约](../01-agents/agent-contract.md)
- [验证系统](../06-verification/README.md)
