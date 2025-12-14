# 对抗验证模式

## 概述

对抗验证通过 Executor → Challenger → Arbiter 三阶段流程，对高风险任务进行严格验证。

## 执行流程

```
Step + AgentCall
       │
       ▼
┌─────────────────┐
│  ExecutorAgent  │  执行任务，生成结果
└────────┬────────┘
         │ Result
         ▼
┌─────────────────┐
│ ChallengerAgent │  挑战结果，找出问题
├─────────────────┤
│ 验证方面:        │
│ - data_accuracy │
│ - logic_consistency │
│ - edge_cases    │
│ - assumption_validity │
└────────┬────────┘
         │ Challenges
         ▼
┌─────────────────┐
│  ArbiterAgent   │  评估挑战，最终裁决
└────────┬────────┘
         │
         ▼
   Final Decision
```

## 实现

```python
async def verify_with_adversarial(self, step: Step, call: AgentCall) -> VotingResult:
    """对抗验证"""
    adversarial_config = self.config['adversarial']

    # 1. Executor 执行
    executor_result = await self.execute_with_config(
        adversarial_config['executor_config'], step, call
    )

    # 2. Challenger 挑战
    challenges = await self.generate_challenges(
        adversarial_config['challenger_config'],
        step, call, executor_result
    )

    # 3. Arbiter 裁决
    arbiter_verdict = await self.arbitrate(
        adversarial_config['arbiter_config'],
        executor_result, challenges
    )

    return VotingResult(
        mode='adversarial',
        individual_results=[executor_result],
        challenges=challenges,
        decision=arbiter_verdict['decision'],
        decision_reasoning=arbiter_verdict['reasoning'],
    )
```

## Challenger 挑战方面

| 方面 | 说明 | 检查内容 |
|-----|------|---------|
| `data_accuracy` | 数据准确性 | 数值正确性、格式合规、来源可靠 |
| `logic_consistency` | 逻辑一致性 | 推理过程、因果关系、结论合理 |
| `edge_cases` | 边界情况 | 极端值、空值、异常输入 |
| `assumption_validity` | 假设有效性 | 前提条件、默认假设、隐含约束 |

## Challenge 结构

```python
Challenge = {
    'aspect': str,                # 挑战方面
    'challenge': str,             # 挑战内容
    'executor_response': str,     # 执行者响应
    'arbiter_verdict': 'valid' | 'invalid' | 'partial',
    'impact': 'none' | 'minor' | 'major',
}
```

## Arbiter 裁决

```python
async def arbitrate(
    self,
    arbiter_config: Dict,
    executor_result: Dict,
    challenges: List[Challenge]
) -> ArbiterVerdict:
    """仲裁裁决"""
    prompt = f"""
    作为仲裁者，评估以下执行结果和挑战：

    执行结果：
    {executor_result}

    挑战列表：
    {challenges}

    请评估：
    1. 每个挑战是否有效
    2. 有效挑战的影响程度
    3. 最终决策（accept/reject/needs_human/needs_retry）
    4. 决策理由
    """

    response = await self.llm.generate(
        prompt,
        model=arbiter_config['model'],
        schema=ArbiterVerdictSchema,
    )

    return response
```

## 裁决结果

| 决策 | 说明 | 后续动作 |
|-----|------|---------|
| `accept` | 结果可接受 | 继续执行 |
| `reject` | 结果被拒绝 | 重新执行或标记失败 |
| `needs_human` | 需要人工介入 | 暂停等待确认 |
| `needs_retry` | 需要重试 | 使用不同参数重试 |

## 配置

```yaml
adversarial:
  executor_config:
    model: "gpt-4"
    timeout_ms: 60000

  challenger_config:
    model: "claude-3-opus"          # 建议用不同模型
    challenge_aspects:
      - data_accuracy
      - logic_consistency
      - edge_cases
      - assumption_validity
    max_challenges: 5
    timeout_ms: 30000

  arbiter_config:
    model: "gpt-4-turbo"
    timeout_ms: 30000
```

## 模型选择建议

为了获得更好的对抗效果，建议使用不同的模型：

| 角色 | 推荐模型 | 原因 |
|-----|---------|-----|
| Executor | GPT-4 | 强大的执行能力 |
| Challenger | Claude-3-Opus | 出色的分析和质疑能力 |
| Arbiter | GPT-4-Turbo | 平衡的判断力 |

## 成本控制

对抗验证成本较高（3 次模型调用），需要控制：

```yaml
cost_limits:
  max_verification_cost_usd: 1.0
  fallback_to_single_on_budget: true
```

## 相关文档

- [验证系统概述](./README.md)
- [投票模式](./voting-mode.md)
- [验证配置](./verification-config.md)
