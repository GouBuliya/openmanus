# 记忆系统

## 概述

记忆系统让平台"越用越聪明"：通过记忆存储、检索和更新，积累执行经验，优化后续任务规划与执行。

## 存储架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Memory Store                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │ Vector Store  │  │   Postgres    │  │    Redis      │       │
│  │ (Embeddings)  │  │ (Structured)  │  │ (Hot Cache)   │       │
│  │               │  │               │  │               │       │
│  │ - 语义检索    │  │ - 元数据索引  │  │ - 热点缓存    │       │
│  │ - 相似匹配    │  │ - 关系查询    │  │ - 会话状态    │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## 三级内存模型

```
┌─────────────────────────────────────────────────────────────────┐
│                    Memory Hierarchy                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  L1: Hot Memory (Redis) - 毫秒级访问                            │
│  ├── 当前活跃任务上下文                                          │
│  ├── 最近 N 分钟的执行状态                                       │
│  └── 高频访问的 Pattern Cache                                    │
│                                                                  │
│  L2: Warm Memory (Postgres + pgvector) - 10ms 级访问            │
│  ├── 任务历史和结果                                              │
│  ├── Site Profile                                                │
│  └── Agent Performance 统计                                      │
│                                                                  │
│  L3: Cold Memory (S3/对象存储) - 100ms 级访问                   │
│  ├── 历史证据归档                                                │
│  ├── 过期 Pattern 归档                                           │
│  └── 审计日志归档                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 记忆类型

| 类型 | 说明 | 用途 |
|-----|------|-----|
| **Task Pattern** | 任务模式缓存 | 相似任务的快速规划 |
| **Failure Knowledge** | 失败知识库 | 失败原因与解决方案映射 |
| **Site Profile** | 站点/应用画像 | 目标网站结构特征和历史经验 |
| **Agent Performance** | 智能体性能统计 | 路由优化 |

## 核心流程

### 1. 记忆检索

```python
async def retrieve_context(self, task: Dict) -> MemoryContext:
    """为任务检索相关记忆上下文"""
    task_embedding = await self.embed(task['intent'])

    # 并行检索
    similar_patterns, site_profile, known_failures = await asyncio.gather(
        self.find_similar_patterns(task_embedding, top_k=3),
        self.get_site_profile(task.get('target_domain')),
        self.find_relevant_failures(task_embedding, top_k=5),
    )

    return MemoryContext(
        similar_tasks=similar_patterns,
        site_profile=site_profile,
        known_issues=known_failures,
    )
```

### 2. 记忆更新

```python
async def update_after_execution(self, task: Dict, result: Dict):
    """执行后更新记忆"""
    if result['status'] == 'success':
        await self.update_success_pattern(task, result)
        await self.update_agent_performance(task, result, success=True)
    else:
        await self.update_failure_knowledge(task, result)
        await self.update_agent_performance(task, result, success=False)

    # 更新站点画像
    if 'site_observations' in result:
        await self.update_site_profile(result['site_observations'])
```

### 3. 层级迁移

- **降级 (Demote)**：长时间未访问的数据自动降级到下一层
- **晋升 (Promote)**：高频访问的数据自动晋升到上一层

## 文档索引

| 文档 | 内容 |
|------|------|
| [记忆类型](./memory-types.md) | Task Pattern、Failure Knowledge、Site Profile、Agent Performance |
| [记忆检索](./memory-retrieval.md) | 向量检索、缓存策略 |
| [生命周期管理](./memory-lifecycle.md) | 分层存储、自动迁移、任务级作用域、压力响应 |
| [配置参考](./memory-config.md) | 完整配置选项 |

## 快速参考

### MemoryContext 结构

```python
MemoryContext = {
    'similar_tasks': List[TaskPattern],   # 相似任务的历史执行
    'site_profile': SiteProfile,          # 目标站点画像
    'known_issues': List[FailureKnowledge], # 已知问题和解决方案
    'recommended_strategies': List[str],  # 推荐策略
}
```

### 层级迁移阈值

| 层级 | 降级条件 | 晋升条件 |
|-----|---------|---------|
| Hot → Warm | 空闲 > 5 分钟 | - |
| Warm → Cold | 空闲 > 1 天 | 访问次数 > 10 → Hot |
| Cold | 保留期满删除 | 访问次数 > 10 → Warm |
