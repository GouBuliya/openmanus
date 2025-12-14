# 意图协商机制

## 概述

在任务执行前，通过 NegotiatorAgent 澄清用户意图，减少歧义，提高执行成功率。

## 协商流程

```
用户输入（可能模糊）
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                  NegotiatorAgent                     │
├──────────────────────────────────────────────────────┤
│  1. 意图解析                                          │
│     - 提取核心目标                                    │
│     - 识别实体（人/物/地点/时间）                     │
│     - 检测隐含需求                                    │
│     - 标记歧义点                                      │
│                                                      │
│  2. 上下文补全                                        │
│     - 查询用户历史偏好（Memory）                      │
│     - 推断缺失参数                                    │
│     - 检索相似任务规划                                │
│                                                      │
│  3. 约束推导                                          │
│     - 风险评估                                        │
│     - 权限检查                                        │
│     - 资源预估                                        │
│     - 成本预估                                        │
│                                                      │
│  4. 协商对话（按需）                                  │
│     - 生成澄清问题                                    │
│     - 提供选项                                        │
│     - 确认理解                                        │
└──────────────────────────────────────────────────────┘
       │
       ▼
结构化 Task Spec（明确）
```

## 协商策略

根据意图理解置信度采取不同策略：

| 置信度 | 策略 | 行为 |
|--------|------|------|
| **> 0.95** | 直接执行 | 跳过确认，直接生成 TaskSpec |
| **0.85 - 0.95** | 快速确认 | 展示理解摘要，请求简单确认 |
| **0.70 - 0.85** | 重点澄清 | 针对 1-2 个关键歧义点提问 |
| **0.50 - 0.70** | 多轮对话 | 系统性澄清多个方面 |
| **< 0.50** | 引导式询问 | 通过结构化问题引导用户描述 |

## 文档索引

| 文档 | 内容 |
|------|------|
| [NegotiatorAgent](./negotiator-agent.md) | Agent 实现、处理流程 |
| [协商配置](./negotiation-config.md) | 配置选项参考 |

## NegotiationSession 结构

```python
NegotiationSession = {
    'session_id': str,
    'created_at': datetime,

    # === 原始输入 ===
    'raw_input': {
        'text': str,                      # 原始用户输入
        'attachments': List[str],         # 附件（截图/文件）
        'context': str,                   # 对话上下文
    },

    # === 意图解析结果 ===
    'parsed_intent': {
        'goal': str,                      # 核心目标
        'action_type': str,               # 动作类型
        'entities': List[Entity],         # 识别的实体
        'constraints_inferred': Dict,     # 推断的约束
    },

    # === 歧义检测 ===
    'ambiguities': List[Ambiguity],

    # === 用户偏好 ===
    'user_preferences': UserPreferences,

    # === 资源与成本预估 ===
    'estimation': {
        'estimated_steps': int,
        'estimated_duration_ms': int,
        'estimated_cost_usd': float,
        'required_capabilities': List[str],
        'risk_level': 'low' | 'medium' | 'high',
    },

    # === 协商状态 ===
    'negotiation_state': {
        'rounds': int,
        'questions_asked': List[str],
        'user_responses': List[str],
        'confidence': float,
    },

    # === 最终输出 ===
    'final_spec': TaskSpec | None,
    'status': 'in_progress' | 'confirmed' | 'cancelled',
}
```

## 快速参考

### 歧义结构

```python
Ambiguity = {
    'aspect': str,                # 哪方面不明确
    'description': str,           # 描述
    'options': [
        {
            'value': str,
            'description': str,
            'is_default': bool,
        }
    ],
    'question': str,              # 澄清问题
    'resolved': bool,
    'resolution': str,
}
```

### 用户偏好

```python
UserPreferences = {
    'time_preference': str,           # '早班机' / '晚班机'
    'price_sensitivity': 'low' | 'medium' | 'high',
    'risk_tolerance': 'low' | 'medium' | 'high',
    'brand_preferences': List[str],
    'historical_choices': List[Dict],
}
```

## 相关文档

- [执行流程](../02-orchestration/execution-flow.md)
- [记忆系统](../04-memory/README.md)
