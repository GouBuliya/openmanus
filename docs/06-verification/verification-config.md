# 验证配置

## 完整配置

```yaml
verification:
  # ==================== 默认模式 ====================
  default_mode: "single"

  # ==================== 自动升级 ====================
  auto_escalation:
    enabled: true
    risk_high_mode: "voting"
    financial_mode: "adversarial"
    amount_threshold_usd: 100

  # ==================== Voting 配置 ====================
  voting:
    default_voters: 3
    default_models: ["gpt-4", "claude-3-opus", "deepseek-v3"]
    consensus_strategy: "majority"    # unanimous / majority / weighted
    min_agreement_ratio: 0.67
    timeout_per_voter_ms: 30000
    tie_breaker: "highest_confidence"

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

  # ==================== Adversarial 配置 ====================
  adversarial:
    executor_config:
      model: "gpt-4"
      timeout_ms: 60000

    challenger_config:
      model: "claude-3-opus"
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

  # ==================== 触发条件 ====================
  triggers:
    risk_levels: ["high", "critical"]
    action_types:
      - purchase
      - transfer
      - delete
      - send_message
      - sign_contract
    amount_threshold_usd: 100.0
    custom_rules:
      - condition: 'domain in ["bank.com", "payment.com"]'
        mode: adversarial

  # ==================== 成本控制 ====================
  cost_limits:
    max_verification_cost_usd: 1.0
    fallback_to_single_on_budget: true
```

## 触发规则引擎

```python
class VerificationTriggerEngine:
    """多 Agent 协商的自动触发规则引擎"""

    def _load_rules(self) -> List[TriggerRule]:
        return [
            # 基于风险等级
            TriggerRule(
                name='high_risk_auto_voting',
                condition=lambda ctx: ctx.step.risk_level == 'high',
                action=VerificationMode.VOTING,
                priority=100,
            ),
            TriggerRule(
                name='critical_risk_adversarial',
                condition=lambda ctx: ctx.step.risk_level == 'critical',
                action=VerificationMode.ADVERSARIAL,
                priority=110,
            ),

            # 基于动作类型
            TriggerRule(
                name='financial_action',
                condition=lambda ctx: ctx.step.action_type in ['purchase', 'transfer', 'payment'],
                action=VerificationMode.ADVERSARIAL,
                priority=100,
            ),
            TriggerRule(
                name='destructive_action',
                condition=lambda ctx: ctx.step.action_type in ['delete', 'cancel', 'revoke'],
                action=VerificationMode.VOTING,
                priority=90,
            ),

            # 基于金额阈值
            TriggerRule(
                name='amount_threshold_high',
                condition=lambda ctx: ctx.extract_amount() >= 1000,
                action=VerificationMode.ADVERSARIAL,
                priority=90,
            ),

            # 基于历史表现
            TriggerRule(
                name='low_success_rate_domain',
                condition=lambda ctx: ctx.memory.get_domain_success_rate(ctx.domain) < 0.7,
                action=VerificationMode.VOTING,
                priority=70,
            ),
            TriggerRule(
                name='first_time_domain',
                condition=lambda ctx: not ctx.memory.has_site_profile(ctx.domain),
                action=VerificationMode.VOTING,
                priority=60,
            ),

            # 基于执行上下文
            TriggerRule(
                name='retry_escalation',
                condition=lambda ctx: ctx.retry_count >= 2,
                action=VerificationMode.VOTING,
                priority=70,
            ),
        ]

    def evaluate(self, context: TriggerContext) -> VerificationDecision:
        matched_rules = [rule for rule in self.rules if rule.condition(context)]

        if not matched_rules:
            return VerificationDecision(
                mode=VerificationMode.SINGLE,
                triggered_by=None,
                explicit_override=False,
            )

        top_rule = max(matched_rules, key=lambda r: r.priority)

        return VerificationDecision(
            mode=top_rule.action,
            triggered_by=top_rule.name,
            matched_rules=[r.name for r in matched_rules],
            explicit_override=False,
        )
```

## 显式调用 API

```python
class VerificationAPI:
    """显式验证调用接口"""

    @staticmethod
    def force_voting(step: Step, config: VotingConfig = None) -> Step:
        """强制该 Step 使用投票验证"""
        step.verification = {
            'mode': 'voting',
            'explicit': True,
            'config': config or VotingConfig.default(),
        }
        return step

    @staticmethod
    def force_adversarial(step: Step, config: AdversarialConfig = None) -> Step:
        """强制该 Step 使用对抗验证"""
        step.verification = {
            'mode': 'adversarial',
            'explicit': True,
            'config': config or AdversarialConfig.default(),
        }
        return step

    @staticmethod
    def force_single(step: Step) -> Step:
        """强制跳过多 Agent 验证（需要审计日志）"""
        step.verification = {
            'mode': 'single',
            'explicit': True,
            'skip_reason_required': True,
        }
        return step
```

## 规则优先级

| 优先级 | 规则类型 | 示例 |
|-------|---------|-----|
| 110 | 严重风险 | critical_risk_adversarial |
| 100 | 高风险/金融 | high_risk, financial_action |
| 90 | 金额阈值/破坏性 | amount_threshold, destructive_action |
| 70 | 历史/重试 | low_success_rate, retry_escalation |
| 60 | 首次访问 | first_time_domain |

## 环境变量

```bash
# 开关
VERIFICATION_AUTO_ESCALATION_ENABLED=true

# 模式
VERIFICATION_DEFAULT_MODE=single
VERIFICATION_HIGH_RISK_MODE=voting
VERIFICATION_FINANCIAL_MODE=adversarial

# 阈值
VERIFICATION_AMOUNT_THRESHOLD_USD=100

# 成本
VERIFICATION_MAX_COST_USD=1.0
```

## 相关文档

- [验证系统概述](./README.md)
- [投票模式](./voting-mode.md)
- [对抗模式](./adversarial-mode.md)
