# 记忆类型

## Task Pattern（任务模式缓存）

存储成功执行的任务规划模板，用于相似任务的快速规划。

```python
TaskPattern = {
    'id': str,
    'task_signature': str,           # 任务签名（用于语义匹配）
    'embedding': List[float],        # 向量表示

    'successful_plan': {
        'steps': List[Step],         # 成功的步骤规划
        'dag_structure': str,        # DAG 结构描述
    },

    'execution_stats': {
        'success_count': int,
        'avg_duration_ms': int,
        'avg_cost_usd': float,
    },

    'applicable_contexts': List[str], # 适用场景
    'created_at': datetime,
    'last_used_at': datetime,
}
```

### 使用场景

1. **规划加速**：检索相似任务，复用历史规划
2. **成本预估**：基于历史统计预估任务成本
3. **策略推荐**：推荐适用的执行策略

---

## Failure Knowledge（失败知识库）

记录失败原因与解决方案的映射关系。

```python
FailureKnowledge = {
    'id': str,
    'failure_signature': str,        # 失败特征签名
    'embedding': List[float],        # 向量表示

    'failure_pattern': {
        'error_type': str,           # 错误类型
        'error_message': str,        # 错误信息
        'context_features': Dict,    # 上下文特征
    },

    'solutions': [
        {
            'strategy': str,         # 解决策略
            'success_rate': float,   # 成功率
            'steps': List[str],      # 解决步骤
        }
    ],

    'root_causes': List[str],        # 根因分析
}
```

### 使用场景

1. **失败预防**：检测相似失败模式，提前规避
2. **自动恢复**：匹配已知问题，应用解决方案
3. **重试策略**：基于历史成功率选择重试策略

---

## Site Profile（站点/应用画像）

存储目标网站或应用的结构特征和历史交互经验。

```python
SiteProfile = {
    'id': str,
    'domain': str,                   # 域名/包名
    'type': 'web' | 'mobile_app',

    'structure': {
        'key_pages': Dict,           # 关键页面结构
        'navigation_paths': List,    # 导航路径
        'element_patterns': Dict,    # 元素定位模式
    },

    'anti_automation': {
        'captcha_types': List[str],  # 验证码类型
        'rate_limits': Dict,         # 频率限制
        'detection_methods': List,   # 检测方法
    },

    'selector_evolution': [          # Selector 演化历史
        {
            'element': str,
            'old_selector': str,
            'new_selector': str,
            'changed_at': datetime,
        }
    ],

    'last_crawled_at': datetime,
}
```

### 使用场景

1. **元素定位**：使用历史有效的选择器
2. **反爬规避**：了解站点的反自动化措施
3. **变更适应**：记录选择器演化，快速修复

---

## Agent Performance（智能体性能统计）

记录各 Agent 的执行表现，用于路由优化。

```python
AgentPerformance = {
    'agent_id': str,
    'capability': str,

    'metrics': {
        'total_calls': int,
        'success_rate': float,
        'avg_latency_ms': float,
        'avg_cost_usd': float,
        'p99_latency_ms': float,
    },

    'by_task_type': Dict[str, Dict], # 按任务类型细分
    'recent_failures': List[Dict],   # 近期失败记录
    'updated_at': datetime,
}
```

### 使用场景

1. **智能路由**：选择最适合的 Agent 处理任务
2. **负载均衡**：根据性能分配任务
3. **异常检测**：识别性能下降的 Agent

---

## 内存条目元数据

```python
@dataclass
class MemoryEntry:
    """内存条目元数据"""
    id: str
    type: MemoryType  # TASK_CONTEXT | PATTERN | EVIDENCE | PROFILE
    created_at: datetime
    last_accessed_at: datetime
    access_count: int
    size_bytes: int
    ttl_seconds: int
    tier: MemoryTier  # HOT | WARM | COLD

    # 引用计数（用于安全回收）
    ref_count: int = 0

    # 所属任务（用于级联回收）
    task_id: Optional[str] = None

    # 是否可淘汰（某些关键数据需保护）
    evictable: bool = True
```

### 类型枚举

```python
class MemoryType(Enum):
    TASK_CONTEXT = 'task_context'
    PATTERN = 'pattern'
    EVIDENCE = 'evidence'
    PROFILE = 'profile'

class MemoryTier(Enum):
    HOT = 'hot'      # Redis
    WARM = 'warm'    # Postgres + pgvector
    COLD = 'cold'    # S3/对象存储
```

## 相关文档

- [记忆系统概述](./README.md)
- [记忆检索](./memory-retrieval.md)
- [生命周期管理](./memory-lifecycle.md)
