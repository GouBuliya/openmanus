# 完整执行流程

## 端到端流程图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           完整执行流程 (v2)                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  用户输入                                                                    │
│      │                                                                       │
│      ▼                                                                       │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  NegotiatorAgent (意图协商)                                    ║          │
│  ║  - 意图解析 → 歧义检测 → 用户偏好查询 → 协商对话               ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│      │                                                                       │
│      ▼ TaskSpec                                                              │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  PlannerAgent                                                  ║          │
│  ║  - 生成 Steps with deps[] (DAG 结构)                          ║          │
│  ║  - 注入 Memory Context (相似任务、站点画像)                    ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│      │                                                                       │
│      ▼ DAG[Steps]                                                            │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  DAG Scheduler (层级化 Kahn 算法)                              ║          │
│  ║  - 拓扑排序 → [[L0], [L1], ..., [Ln]]                         ║          │
│  ║  - 层内并行、层间串行                                          ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│      │                                                                       │
│      ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Layer-by-Layer Execution                                           │    │
│  │  ┌───────────────────────────────────────────────────────────────┐ │    │
│  │  │ Level N: [Step1, Step2, Step3] ─────────────┐                 │ │    │
│  │  │      │                                       │                 │ │    │
│  │  │      ▼ (并行)                                ▼                 │ │    │
│  │  │  ╔════════════════════════════════════════════════════════╗  │ │    │
│  │  │  ║  AgentCall (Contract v2)                               ║  │ │    │
│  │  │  ║  + context.upstream_results (自动注入)                  ║  │ │    │
│  │  │  ║  + context.memory_context (自动注入)                    ║  │ │    │
│  │  │  ╚════════════════════════════════════════════════════════╝  │ │    │
│  │  │      │                                                        │ │    │
│  │  │      ▼                                                        │ │    │
│  │  │  ╔════════════════════════════════════════════════════════╗  │ │    │
│  │  │  ║  Verification (按 risk_level 选择模式)                  ║  │ │    │
│  │  │  ║  - Single: 直接执行                                     ║  │ │    │
│  │  │  ║  - Voting: 多 Agent 投票                                ║  │ │    │
│  │  │  ║  - Adversarial: 执行→挑战→仲裁                         ║  │ │    │
│  │  │  ╚════════════════════════════════════════════════════════╝  │ │    │
│  │  │      │                                                        │ │    │
│  │  │      ▼                                                        │ │    │
│  │  │  ╔════════════════════════════════════════════════════════╗  │ │    │
│  │  │  ║  CriticAgent (验收)                                     ║  │ │    │
│  │  │  ║  → accept / retry / switch_resource / replan            ║  │ │    │
│  │  │  ╚════════════════════════════════════════════════════════╝  │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  │                          │                                          │    │
│  │                          ▼                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────┐ │    │
│  │  │ Level N+1: 等待 Level N 完成后执行                            │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                          │                                                   │
│                          ▼                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║  Memory Update                                                 ║          │
│  ║  - 存储成功模式 (Task Pattern)                                 ║          │
│  ║  - 记录失败教训 (Failure Knowledge)                            ║          │
│  ║  - 更新站点画像 (Site Profile)                                 ║          │
│  ║  - 统计 Agent 性能 (Agent Performance)                         ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│                          │                                                   │
│                          ▼                                                   │
│                    Task Result                                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 阶段详解

### 1. 意图协商（Intent Negotiation）

```python
async def negotiate_intent(raw_input: str, user_id: str) -> TaskSpec:
    """意图协商流程"""
    session = NegotiationSession(raw_input=raw_input)

    # 1. 意图解析
    parsed_intent = await negotiator.parse_intent(raw_input)

    # 2. 检索用户偏好（从 Memory）
    user_preferences = await memory.get_user_preferences(user_id)

    # 3. 检测歧义
    ambiguities = await negotiator.detect_ambiguities(parsed_intent, user_preferences)

    # 4. 计算置信度
    confidence = calculate_confidence(parsed_intent, ambiguities)

    # 5. 根据置信度决策
    if confidence > 0.95:
        # 直接生成 TaskSpec
        return await generate_task_spec(parsed_intent)
    elif confidence > 0.85:
        # 快速确认
        await send_confirmation_summary()
        return await wait_for_user_confirmation()
    else:
        # 多轮对话澄清
        return await clarification_dialogue(ambiguities)
```

### 2. 任务规划（Planning）

```python
async def plan_task(task_spec: TaskSpec) -> List[Step]:
    """任务规划流程"""
    # 1. 检索相关记忆
    memory_context = await memory.retrieve_context(task_spec)

    # 2. 调用 PlannerAgent
    steps = await planner_agent.generate_steps(
        task_spec=task_spec,
        memory_context=memory_context,
    )

    # 3. 验证 DAG 合法性
    validation = validate_dag(steps)
    if not validation['valid']:
        raise PlanValidationError(validation['issues'])

    return steps
```

### 3. DAG 调度执行

```python
async def execute_dag(steps: List[Step]) -> Dict[str, StepResult]:
    """DAG 调度执行"""
    scheduler = DAGScheduler(steps)
    levels = scheduler.topological_sort()

    results = {}
    for level_idx, level_ids in enumerate(levels):
        # 层内并行执行
        tasks = [
            execute_step(steps[sid], results)
            for sid in level_ids
        ]
        level_results = await asyncio.gather(*tasks, return_exceptions=True)

        for step_id, result in zip(level_ids, level_results):
            results[step_id] = result

    return results
```

### 4. 单步执行

```python
async def execute_step(step: Step, upstream_results: Dict) -> StepResult:
    """单步执行流程"""
    # 1. 注入上下文
    step = inject_context(step, upstream_results)

    # 2. 获取租约
    lease = await lease_manager.acquire(
        capabilities=step.capabilities_required,
        label_selector=step.label_selector,
    )

    try:
        # 3. 路由到 Specialist Agent
        agent = await router.select_agent(step.capabilities_required)

        # 4. 构建 AgentCall
        call = build_agent_call(step, lease)

        # 5. 执行（按风险级别选择验证模式）
        if step.constraints.risk_level == 'high':
            result = await execute_with_verification(agent, call)
        else:
            result = await agent.execute(call)

        # 6. Critic 验收
        decision = await critic_agent.evaluate(step, result)

        # 7. 根据决策处理
        return await handle_decision(step, result, decision)

    finally:
        # 8. 释放租约
        await lease_manager.release(lease.id)
```

### 5. 验证执行

```python
async def execute_with_verification(agent: Agent, call: AgentCall) -> AgentResult:
    """带验证的执行"""
    verification_config = call.verification

    if verification_config.mode == 'voting':
        return await execute_with_voting(call, verification_config)

    elif verification_config.mode == 'adversarial':
        return await execute_with_adversarial(call, verification_config)

    else:  # single
        return await agent.execute(call)


async def execute_with_voting(call: AgentCall, config: Dict) -> AgentResult:
    """多 Agent 投票执行"""
    # 并行执行多个 Agent
    results = await asyncio.gather(*[
        execute_with_model(call, model)
        for model in config.voter_models
    ])

    # 分析共识
    consensus = analyze_consensus(results, config.consensus_strategy)

    if consensus.reached:
        return consensus.final_result
    else:
        # 需要仲裁
        return await arbiter_agent.resolve(results)
```

### 6. 记忆更新

```python
async def update_memory(task: Task, results: Dict[str, StepResult]):
    """执行后更新记忆"""
    task_result = aggregate_results(results)

    if task_result.status == 'success':
        # 存储成功模式
        await memory.store_pattern(task, results)
        # 更新 Agent 性能统计
        await memory.update_agent_performance(results)
    else:
        # 记录失败知识
        await memory.store_failure_knowledge(task, results)

    # 更新站点画像（无论成功失败）
    if site_observations := extract_site_observations(results):
        await memory.update_site_profile(site_observations)
```

## 关键组件交互

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  Task API   │────▶│Orchestrator │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
             ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
             │  Planner    │           │   Router    │           │  Scheduler  │
             │   Agent     │           │             │           │             │
             └──────┬──────┘           └──────┬──────┘           └──────┬──────┘
                    │                         │                         │
                    ▼                         ▼                         ▼
             ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
             │DAG Scheduler│           │  Specialist │           │   Lease     │
             │             │           │   Agents    │           │  Manager    │
             └─────────────┘           └─────────────┘           └─────────────┘
```

## 错误处理

### 重试策略

| 错误类型 | 策略 | 说明 |
|---------|------|------|
| 网络超时 | retry | 指数退避重试 |
| 资源故障 | switch_resource | 切换到其他资源 |
| 验证失败 | retry + 调整参数 | 重试时调整执行参数 |
| 规划错误 | replan | 触发重新规划 |
| 人工介入 | needs_user | 等待用户确认 |

### 降级策略

```python
async def handle_degradation(step: Step, error: Exception) -> StepResult:
    """处理降级"""
    if isinstance(error, ResourceExhaustedError):
        # 降级到低优先级资源
        return await execute_with_degraded_resource(step)

    elif isinstance(error, ModelOverloadError):
        # 降级到备用模型
        return await execute_with_fallback_model(step)

    elif isinstance(error, TimeoutError):
        # 返回部分结果
        return StepResult(status='partial', outputs=step.partial_outputs)

    else:
        raise
```
