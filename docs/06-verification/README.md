# 验证系统

## 概述

对于高风险任务，通过多个 Agent 独立执行并投票，或通过挑战者-仲裁者模式验证结果，提高可靠性。

## 验证模式

### A. Single 模式（默认）

单个 Agent 执行，CriticAgent 验收。适用于低风险任务。

### B. Voting 模式（多数投票）

```
                     高风险 Step
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     ┌─────────┐    ┌─────────┐    ┌─────────┐
     │ Agent A │    │ Agent B │    │ Agent C │
     │(GPT-4)  │    │(Claude) │    │(DeepSeek)│
     └────┬────┘    └────┬────┘    └────┬────┘
          │               │               │
          ▼               ▼               ▼
     Result A        Result B        Result C
          │               │               │
          └───────────────┼───────────────┘
                          ▼
                 ┌─────────────────┐
                 │  VotingAgent    │
                 ├─────────────────┤
                 │ - 结果对比      │
                 │ - 一致性检查    │
                 │ - 冲突检测      │
                 │ - 置信度评估    │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ Final Decision  │
                 └─────────────────┘
```

### C. Adversarial 模式（对抗验证）

```
                     高风险 Step
                          │
                          ▼
                 ┌─────────────────┐
                 │  ExecutorAgent  │  ← 执行任务
                 └────────┬────────┘
                          │ Result
                          ▼
                 ┌─────────────────┐
                 │ ChallengerAgent │  ← 专门找问题
                 ├─────────────────┤
                 │ - 验证数据准确性│
                 │ - 检查逻辑漏洞  │
                 │ - 模拟边界情况  │
                 │ - 质疑假设前提  │
                 └────────┬────────┘
                          │ Challenges
                          ▼
                 ┌─────────────────┐
                 │  ArbiterAgent   │  ← 最终裁决
                 ├─────────────────┤
                 │ - 评估挑战有效性│
                 │ - 综合判断      │
                 │ - 生成最终结论  │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ Final Decision  │
                 └─────────────────┘
```

## 模式选择

| 场景 | 推荐模式 | 原因 |
|-----|---------|-----|
| 低风险任务 | Single | 成本低、速度快 |
| 高风险任务 | Voting | 多方验证、共识决策 |
| 金融交易 | Adversarial | 对抗检验、严格验证 |
| 破坏性操作 | Voting | 多方确认 |
| 首次访问站点 | Voting | 缺乏历史经验 |

## 文档索引

| 文档 | 内容 |
|------|------|
| [投票模式](./voting-mode.md) | VotingAgent 实现、共识分析 |
| [对抗模式](./adversarial-mode.md) | Challenger/Arbiter 设计 |
| [验证配置](./verification-config.md) | 触发规则、配置选项 |

## VotingResult 结构

```python
VotingResult = {
    'verification_id': str,
    'mode': 'voting' | 'adversarial',
    'created_at': datetime,

    # === 个体结果 ===
    'individual_results': [
        {
            'voter_id': str,
            'model': str,
            'result': Dict[str, Any],
            'confidence': float,
            'reasoning': str,
            'execution_time_ms': int,
            'cost_usd': float,
        }
    ],

    # === 共识分析 ===
    'consensus': {
        'reached': bool,
        'agreement_ratio': float,
        'final_result': Dict[str, Any],
        'confidence': float,
        'decision_method': str,  # 'unanimous' / 'majority' / 'arbiter'
    },

    # === 冲突分析 ===
    'conflicts': List[Conflict],

    # === 对抗验证特有 ===
    'challenges': List[Challenge] | None,

    # === 最终决策 ===
    'decision': 'accept' | 'reject' | 'needs_human' | 'needs_retry',
    'decision_reasoning': str,
}
```

## 触发条件

| 条件类型 | 示例 | 触发模式 |
|---------|------|---------|
| 风险等级 | `risk_level == 'high'` | Voting |
| 风险等级 | `risk_level == 'critical'` | Adversarial |
| 动作类型 | `purchase, transfer, payment` | Adversarial |
| 动作类型 | `delete, cancel, revoke` | Voting |
| 金额阈值 | `amount >= 1000 USD` | Adversarial |
| 历史表现 | `domain_success_rate < 0.7` | Voting |
| 首次访问 | `!has_site_profile(domain)` | Voting |
| 重试次数 | `retry_count >= 2` | Voting |

## 相关文档

- [执行流程](../02-orchestration/execution-flow.md)
- [Step 生命周期](../02-orchestration/step-lifecycle.md)
