# 记忆系统配置

## 完整配置示例

```yaml
memory:
  enabled: true

  # ==================== 向量存储配置 ====================
  vector_store:
    type: "pgvector"  # pgvector / milvus / pinecone
    embedding_model: "text-embedding-3-small"
    embedding_dim: 1536

    # 备选嵌入模型
    fallback_model: "bge-m3"
    fallback_dim: 1024

  # ==================== 检索配置 ====================
  retrieval:
    similarity_threshold: 0.85
    max_results: 5
    cache_ttl_seconds: 300

  # ==================== 层级配置 ====================
  tiers:
    hot:
      backend: redis
      max_size_mb: 512
      default_ttl_seconds: 300
    warm:
      backend: postgres
      max_size_mb: 2048
      default_ttl_seconds: 86400
    cold:
      backend: s3
      max_size_mb: unlimited
      default_ttl_seconds: 2592000  # 30 days

  # ==================== 迁移策略 ====================
  migration:
    demote_after_idle_seconds:
      hot_to_warm: 300        # 5 分钟
      warm_to_cold: 86400     # 1 天
    promote_after_access_count: 10

  # ==================== GC 配置 ====================
  gc:
    interval_seconds: 60
    pressure_threshold: 0.8
    lru_eviction_ratio: 0.2

  # ==================== 保留策略 ====================
  retention:
    task_patterns_days: 180
    failure_knowledge_days: 365
    site_profiles_days: 90
    task_context_days: 7
    evidence_days: 90
    audit_logs_days: 365

  # ==================== 更新配置 ====================
  update:
    batch_size: 100
    async_update: true
```

## 配置说明

### 向量存储

| 配置项 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| `type` | string | pgvector | 向量存储类型 |
| `embedding_model` | string | text-embedding-3-small | 嵌入模型 |
| `embedding_dim` | int | 1536 | 向量维度 |

### 检索参数

| 配置项 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| `similarity_threshold` | float | 0.85 | 最低相似度阈值 |
| `max_results` | int | 5 | 返回结果数上限 |
| `cache_ttl_seconds` | int | 300 | 缓存 TTL |

### 层级存储

| 层级 | 后端 | 访问延迟 | 容量限制 | TTL |
|-----|------|---------|---------|-----|
| Hot | Redis | ~1ms | 512MB | 5min |
| Warm | Postgres | ~10ms | 2GB | 1day |
| Cold | S3 | ~100ms | 无限 | 30days |

### GC 参数

| 配置项 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| `interval_seconds` | int | 60 | GC 执行间隔 |
| `pressure_threshold` | float | 0.8 | 触发压力回收的阈值 |
| `lru_eviction_ratio` | float | 0.2 | LRU 淘汰目标比例 |

## 环境变量覆盖

```bash
# 向量存储
MEMORY_VECTOR_STORE_TYPE=pgvector
MEMORY_EMBEDDING_MODEL=text-embedding-3-small

# Redis (Hot tier)
MEMORY_REDIS_URL=redis://localhost:6379
MEMORY_REDIS_MAX_SIZE_MB=512

# Postgres (Warm tier)
MEMORY_POSTGRES_URL=postgresql://localhost/manus
MEMORY_POSTGRES_MAX_SIZE_MB=2048

# S3 (Cold tier)
MEMORY_S3_BUCKET=manus-memory-cold
MEMORY_S3_REGION=us-west-2

# GC
MEMORY_GC_INTERVAL=60
MEMORY_GC_PRESSURE_THRESHOLD=0.8
```

## Redis 配置

```yaml
redis:
  url: "redis://localhost:6379"
  db: 0
  max_connections: 100

  # 持久化
  persistence:
    aof: true
    rdb: true

  # 内存策略
  maxmemory_policy: "allkeys-lru"
```

## Postgres + pgvector 配置

```yaml
postgres:
  url: "postgresql://localhost:5432/manus"
  pool_size: 20

  # pgvector 索引
  vector_index:
    type: "hnsw"
    m: 16
    ef_construction: 64
```

### 索引创建 SQL

```sql
-- 创建 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- Task Patterns 表
CREATE TABLE task_patterns (
    id UUID PRIMARY KEY,
    task_signature TEXT NOT NULL,
    embedding vector(1536),
    successful_plan JSONB,
    execution_stats JSONB,
    applicable_contexts TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    access_count INT DEFAULT 0
);

-- HNSW 索引
CREATE INDEX ON task_patterns
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 时间索引
CREATE INDEX ON task_patterns (last_used_at DESC);
```

## S3 配置

```yaml
s3:
  bucket: "manus-memory-cold"
  region: "us-west-2"

  # 生命周期策略
  lifecycle:
    - prefix: "evidence/"
      transition:
        days: 30
        storage_class: "GLACIER"
      expiration:
        days: 365

    - prefix: "patterns/"
      transition:
        days: 90
        storage_class: "GLACIER"
      expiration:
        days: 730
```

## 性能调优

### 高吞吐场景

```yaml
memory:
  retrieval:
    cache_ttl_seconds: 600  # 延长缓存
    max_results: 3          # 减少结果数

  gc:
    interval_seconds: 120   # 降低 GC 频率

  update:
    batch_size: 200         # 增大批量更新
    async_update: true
```

### 低延迟场景

```yaml
memory:
  tiers:
    hot:
      max_size_mb: 1024     # 增大 Hot 层容量

  migration:
    demote_after_idle_seconds:
      hot_to_warm: 600      # 延长 Hot 层保留
    promote_after_access_count: 5  # 更积极晋升
```

### 成本优化场景

```yaml
memory:
  tiers:
    hot:
      max_size_mb: 256      # 减小 Hot 层
    warm:
      max_size_mb: 1024     # 减小 Warm 层

  retention:
    task_patterns_days: 90  # 缩短保留期
    evidence_days: 30
```

## 相关文档

- [记忆系统概述](./README.md)
- [记忆类型](./memory-types.md)
- [生命周期管理](./memory-lifecycle.md)
