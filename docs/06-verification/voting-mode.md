# 投票模式

## 概述

多个 Agent 独立执行相同任务，通过投票机制达成共识，提高结果可靠性。

## VotingAgent 实现

```python
class VotingAgent:
    def __init__(self, config: VerificationConfig):
        self.config = config

    async def verify_with_voting(self, step: Step, call: AgentCall) -> VotingResult:
        """多 Agent 投票验证"""
        voting_config = self.config['voting']

        # 并行执行所有 voter
        tasks = [
            self.execute_voter(voter_config, step, call)
            for voter_config in voting_config['voter_configs']
        ]
        individual_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤失败的结果
        valid_results = [r for r in individual_results if not isinstance(r, Exception)]

        # 分析共识
        consensus = self.analyze_consensus(valid_results, voting_config)

        # 检测冲突
        conflicts = self.detect_conflicts(valid_results)

        # 生成最终决策
        decision = self.make_decision(consensus, conflicts, voting_config)

        return VotingResult(
            individual_results=valid_results,
            consensus=consensus,
            conflicts=conflicts,
            decision=decision,
        )
```

## 共识分析

```python
def analyze_consensus(self, results: List[Dict], config: Dict) -> Dict:
    """分析投票共识"""
    if not results:
        return {'reached': False, 'agreement_ratio': 0}

    # 提取关键输出字段进行对比
    key_fields = self.extract_key_fields(results)

    # 计算一致率
    agreement_counts = {}
    for field, values in key_fields.items():
        most_common = max(set(values), key=values.count)
        agreement_counts[field] = values.count(most_common) / len(values)

    overall_agreement = sum(agreement_counts.values()) / len(agreement_counts)

    # 根据策略判断是否达成共识
    strategy = config['consensus_strategy']
    min_ratio = config['min_agreement_ratio']

    if strategy == 'unanimous':
        reached = overall_agreement == 1.0
    elif strategy == 'majority':
        reached = overall_agreement >= min_ratio
    else:  # weighted
        reached = self.calculate_weighted_agreement(results, config) >= min_ratio

    return {
        'reached': reached,
        'agreement_ratio': overall_agreement,
        'final_result': self.merge_results(results) if reached else None,
        'confidence': overall_agreement,
    }
```

## 共识策略

### Unanimous（全票通过）

所有 Agent 必须返回相同结果。

```python
reached = overall_agreement == 1.0
```

### Majority（多数投票）

超过指定比例的 Agent 返回相同结果。

```python
reached = overall_agreement >= min_agreement_ratio  # 默认 0.67
```

### Weighted（加权投票）

根据 Agent 权重计算加权一致率。

```python
def calculate_weighted_agreement(self, results: List[Dict], config: Dict) -> float:
    weights = {v['model']: v['weight'] for v in config['voter_configs']}
    total_weight = sum(weights.values())

    # 找出每个字段的加权最大值
    weighted_agreements = []
    for field in key_fields:
        value_weights = defaultdict(float)
        for result in results:
            value = result[field]
            value_weights[value] += weights[result['model']]

        max_weight = max(value_weights.values())
        weighted_agreements.append(max_weight / total_weight)

    return sum(weighted_agreements) / len(weighted_agreements)
```

## 冲突检测

```python
def detect_conflicts(self, results: List[Dict]) -> List[Conflict]:
    """检测结果冲突"""
    conflicts = []
    key_fields = self.extract_key_fields(results)

    for field, values in key_fields.items():
        unique_values = set(values)
        if len(unique_values) > 1:
            conflicts.append(Conflict(
                field=field,
                values=list(unique_values),
                voters=self.get_voters_by_value(results, field),
                resolution=self.suggest_resolution(field, values),
            ))

    return conflicts
```

## 平局处理

| 策略 | 说明 |
|-----|------|
| `highest_confidence` | 选择置信度最高的结果 |
| `first_response` | 选择最先返回的结果 |
| `arbiter` | 调用仲裁 Agent 裁决 |

```python
def resolve_tie(self, results: List[Dict], strategy: str) -> Dict:
    if strategy == 'highest_confidence':
        return max(results, key=lambda r: r['confidence'])
    elif strategy == 'first_response':
        return min(results, key=lambda r: r['execution_time_ms'])
    elif strategy == 'arbiter':
        return await self.call_arbiter(results)
```

## Voter 配置

```python
VoterConfig = {
    'model': str,           # 使用的模型
    'weight': float,        # 投票权重
    'timeout_ms': int,      # 超时时间
    'max_retries': int,     # 最大重试次数
}
```

### 典型配置

```yaml
voter_configs:
  - model: "gpt-4"
    weight: 1.0
    timeout_ms: 30000

  - model: "claude-3-opus"
    weight: 1.0
    timeout_ms: 30000

  - model: "deepseek-v3"
    weight: 0.8
    timeout_ms: 30000
```

## 相关文档

- [验证系统概述](./README.md)
- [对抗模式](./adversarial-mode.md)
- [验证配置](./verification-config.md)
