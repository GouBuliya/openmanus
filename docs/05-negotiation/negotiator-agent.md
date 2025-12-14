# NegotiatorAgent

## 概述

NegotiatorAgent 负责在任务执行前澄清用户意图，通过意图解析、歧义检测和对话澄清，生成明确的 TaskSpec。

## 实现

```python
class NegotiatorAgent:
    def __init__(self, memory: MemoryStore, llm: LLM):
        self.memory = memory
        self.llm = llm

    async def negotiate(self, raw_input: str, user_id: str) -> NegotiationSession:
        session = NegotiationSession(raw_input=raw_input)

        # 1. 意图解析
        session.parsed_intent = await self.parse_intent(raw_input)

        # 2. 检索用户偏好
        session.user_preferences = await self.memory.get_user_preferences(user_id)

        # 3. 检测歧义
        session.ambiguities = await self.detect_ambiguities(
            session.parsed_intent,
            session.user_preferences,
        )

        # 4. 计算置信度
        session.negotiation_state['confidence'] = self.calculate_confidence(session)

        # 5. 根据置信度决定下一步
        if session.negotiation_state['confidence'] > 0.95:
            session.final_spec = await self.generate_task_spec(session)
            session.status = 'confirmed'
        elif session.negotiation_state['confidence'] > 0.85:
            # 生成确认摘要
            session.confirmation_summary = await self.generate_summary(session)
        else:
            # 生成澄清问题
            session.next_questions = self.prioritize_questions(session.ambiguities)

        return session

    async def respond_to_clarification(
        self,
        session: NegotiationSession,
        user_response: str
    ) -> NegotiationSession:
        """处理用户对澄清问题的回答"""
        # 更新歧义解决状态
        session = await self.update_ambiguities(session, user_response)

        # 重新计算置信度
        session.negotiation_state['confidence'] = self.calculate_confidence(session)
        session.negotiation_state['rounds'] += 1

        # 检查是否可以结束协商
        if session.negotiation_state['confidence'] > 0.85:
            session.final_spec = await self.generate_task_spec(session)
            session.status = 'confirmed'

        return session
```

## 处理步骤

### 1. 意图解析

```python
async def parse_intent(self, raw_input: str) -> ParsedIntent:
    """解析用户意图"""
    prompt = f"""
    分析以下用户输入，提取：
    1. 核心目标（goal）
    2. 动作类型（action_type）
    3. 实体（entities）- 人物、地点、时间、产品等
    4. 推断的约束（constraints）

    用户输入：{raw_input}
    """

    response = await self.llm.generate(prompt, schema=ParsedIntentSchema)
    return response
```

### 2. 歧义检测

```python
async def detect_ambiguities(
    self,
    parsed_intent: ParsedIntent,
    user_preferences: UserPreferences
) -> List[Ambiguity]:
    """检测意图中的歧义"""
    ambiguities = []

    # 检查必填信息
    required_fields = self.get_required_fields(parsed_intent.action_type)
    for field in required_fields:
        if not getattr(parsed_intent, field, None):
            ambiguities.append(Ambiguity(
                aspect=field,
                description=f"缺少必填信息: {field}",
                question=self.generate_question(field),
            ))

    # 检查选项冲突
    if parsed_intent.has_multiple_interpretations():
        for interpretation in parsed_intent.interpretations:
            ambiguities.append(Ambiguity(
                aspect='interpretation',
                description="存在多种理解方式",
                options=interpretation.options,
            ))

    return ambiguities
```

### 3. 置信度计算

```python
def calculate_confidence(self, session: NegotiationSession) -> float:
    """计算意图理解置信度"""
    base_confidence = session.parsed_intent.confidence

    # 歧义惩罚
    unresolved = [a for a in session.ambiguities if not a.resolved]
    ambiguity_penalty = len(unresolved) * 0.1

    # 用户偏好加成
    preference_bonus = 0.05 if session.user_preferences else 0

    # 相似任务加成
    similar_task_bonus = 0.05 if session.similar_tasks else 0

    confidence = base_confidence - ambiguity_penalty + preference_bonus + similar_task_bonus
    return max(0, min(1, confidence))
```

### 4. 问题优先级排序

```python
def prioritize_questions(self, ambiguities: List[Ambiguity]) -> List[str]:
    """按优先级排序澄清问题"""
    # 优先级规则：
    # 1. 必填字段缺失
    # 2. 影响安全/成本的歧义
    # 3. 影响执行路径的歧义
    # 4. 其他歧义

    priority_map = {
        'required_field': 100,
        'security': 90,
        'cost': 80,
        'execution_path': 70,
        'preference': 50,
    }

    sorted_ambiguities = sorted(
        ambiguities,
        key=lambda a: priority_map.get(a.category, 0),
        reverse=True
    )

    return [a.question for a in sorted_ambiguities[:3]]  # 每轮最多 3 个问题
```

## 协商终止条件

| 条件 | 结果 |
|-----|------|
| 置信度 > 0.85 | 生成 TaskSpec，状态 = confirmed |
| 轮次 >= max_rounds | 生成当前最佳 TaskSpec，状态 = confirmed |
| 用户取消 | 状态 = cancelled |
| 超时 | 状态 = cancelled |

## 相关文档

- [意图协商概述](./README.md)
- [协商配置](./negotiation-config.md)
