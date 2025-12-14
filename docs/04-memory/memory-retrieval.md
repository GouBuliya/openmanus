# 记忆检索

## 概述

记忆检索系统支持语义相似度检索和结构化查询，为任务规划和执行提供历史上下文。

## 检索器实现

```python
class MemoryRetriever:
    def __init__(self, vector_store, postgres, redis):
        self.vector_store = vector_store
        self.postgres = postgres
        self.redis = redis

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

## 向量相似度检索

```python
async def find_similar_patterns(self, embedding, top_k=3) -> List[TaskPattern]:
    """向量相似度检索"""
    # 先查 Redis 缓存
    cache_key = f"pattern:{hash(tuple(embedding[:10]))}"
    cached = await self.redis.get(cache_key)
    if cached:
        return cached

    # 向量检索
    results = await self.vector_store.search(
        collection='task_patterns',
        vector=embedding,
        top_k=top_k,
        threshold=0.85,
    )

    # 缓存结果（5分钟 TTL）
    await self.redis.setex(cache_key, 300, results)
    return results
```

## 检索流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    Memory Retrieval Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Task Intent                                                     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐                                                │
│  │  Embedding  │  text-embedding-3-small                        │
│  │   Model     │  (1536 维向量)                                  │
│  └──────┬──────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Parallel Retrieval                          │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐           │   │
│  │  │ Pattern   │  │   Site    │  │ Failure   │           │   │
│  │  │ Search    │  │  Profile  │  │ Knowledge │           │   │
│  │  └───────────┘  └───────────┘  └───────────┘           │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │  Memory     │  组装检索结果                                  │
│  │  Context    │                                                │
│  └─────────────┘                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 检索策略

### 1. 相似任务检索

| 参数 | 默认值 | 说明 |
|-----|-------|-----|
| `top_k` | 3 | 返回最相似的 K 个结果 |
| `threshold` | 0.85 | 最低相似度阈值 |
| `cache_ttl` | 300s | 缓存 TTL |

### 2. 站点画像检索

```python
async def get_site_profile(self, domain: str) -> Optional[SiteProfile]:
    """获取站点画像"""
    if not domain:
        return None

    # 精确匹配
    profile = await self.postgres.fetchone(
        "SELECT * FROM site_profiles WHERE domain = $1",
        domain
    )

    if not profile:
        # 尝试父域名匹配
        parent_domain = self._extract_parent_domain(domain)
        profile = await self.postgres.fetchone(
            "SELECT * FROM site_profiles WHERE domain = $1",
            parent_domain
        )

    return profile
```

### 3. 失败知识检索

```python
async def find_relevant_failures(self, embedding, top_k=5) -> List[FailureKnowledge]:
    """检索相关失败知识"""
    results = await self.vector_store.search(
        collection='failure_knowledge',
        vector=embedding,
        top_k=top_k,
        threshold=0.8,
        filter={
            'solutions.success_rate': {'$gt': 0.5}  # 只返回有效解决方案
        }
    )
    return results
```

## 缓存策略

### 多级缓存

```
┌─────────────────────────────────────────────┐
│              Cache Hierarchy                 │
├─────────────────────────────────────────────┤
│                                             │
│  L1: Request-level Cache (内存)             │
│      - 同一请求内的重复检索                  │
│      - TTL: 请求生命周期                     │
│                                             │
│  L2: Hot Cache (Redis)                      │
│      - 热点查询结果                          │
│      - TTL: 5 分钟                           │
│                                             │
│  L3: Warm Cache (Postgres)                  │
│      - 完整数据                              │
│      - 持久化存储                            │
│                                             │
└─────────────────────────────────────────────┘
```

### 缓存键设计

```python
# Pattern 缓存键
pattern_key = f"memory:pattern:{hash(embedding[:10])}"

# Site Profile 缓存键
site_key = f"memory:site:{domain}"

# Agent Performance 缓存键
agent_key = f"memory:agent:{agent_id}:{capability}"
```

## 嵌入模型

```yaml
embedding:
  model: "text-embedding-3-small"  # OpenAI
  dimensions: 1536
  batch_size: 100

  # 备选模型
  fallback:
    model: "bge-m3"  # 本地部署
    dimensions: 1024
```

## 性能优化

### 1. 批量嵌入

```python
async def batch_embed(self, texts: List[str]) -> List[List[float]]:
    """批量生成嵌入向量"""
    batches = [texts[i:i+100] for i in range(0, len(texts), 100)]
    embeddings = []
    for batch in batches:
        result = await self.embedding_model.embed(batch)
        embeddings.extend(result)
    return embeddings
```

### 2. 索引优化

```sql
-- pgvector HNSW 索引
CREATE INDEX ON task_patterns
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 复合索引
CREATE INDEX ON task_patterns (domain, created_at DESC);
```

### 3. 预热策略

```python
async def warmup_cache(self):
    """预热热点缓存"""
    # 加载高频访问的 Pattern
    hot_patterns = await self.postgres.fetch(
        "SELECT * FROM task_patterns ORDER BY access_count DESC LIMIT 100"
    )
    for pattern in hot_patterns:
        await self.redis.set(f"memory:pattern:{pattern['id']}", pattern, ex=3600)
```

## 相关文档

- [记忆系统概述](./README.md)
- [记忆类型](./memory-types.md)
- [生命周期管理](./memory-lifecycle.md)
