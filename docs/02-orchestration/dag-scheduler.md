# DAG 拓扑调度

> 基于论文《基于有向无环图拓扑调度的人工智能代理任务编排系统》，采用 **层级化 Kahn 算法** 实现任务编排。

## 层级化 Kahn 算法

### 核心思想

将 DAG 按拓扑顺序分层，同层任务互不依赖可并行执行。

```
算法流程：
1. 构建依赖图 G 和反向图 G'
2. 计算每个节点的入度 in_degree[v] = |v.deps|
3. 初始化队列 Q ← {v | in_degree[v] = 0}
4. while Q 非空:
     current_level ← Q 中所有节点（同层并行）
     对每个 v ∈ current_level:
       处理 v，更新下游节点入度
       若 in_degree[u] = 0 则加入 Q
5. 输出：[[Level0], [Level1], ..., [LevelK]]
```

### 性能特征

| 指标 | 值 |
|------|-----|
| 时间复杂度 | O(V + E)，V=节点数，E=边数 |
| 调度延迟 | <10ms（500 任务规模） |
| 理论最优 | 层数等于 DAG 中最长路径的节点数（Mirsky 定理） |

## Step 数据结构

```python
Step = {
    # === 基础标识 ===
    'id': str,                        # 步骤唯一标识
    'title': str,                     # 步骤标题

    # === DAG 依赖（核心字段）===
    'deps': List[str],                # 依赖的步骤 ID 列表

    # === 能力要求 ===
    'capabilities_required': List[str],
    'label_selector': Dict,           # 资源标签选择器

    # === 并行控制 ===
    'fanout': int,                    # 并行副本数（单步内）
    'anti_affinity': bool,            # 副本分配到不同资源

    # === 执行控制 ===
    'idempotency_key': str,           # 幂等键（重试保护）
    'timeout_ms': int,                # 超时时间

    # === 输出规范 ===
    'return_spec': {
        'schema_id': str,
        'required_fields': List[str],
    },
    'success_criteria': str,
    'evidence_required': List[str],   # screenshot/video/dom_snapshot/...

    # === 约束 ===
    'constraints': {
        'no_purchase': bool,
        'allowed_domains': List[str],
        'time_budget_ms': int,
        'cost_budget_usd': float,
    },

    # === 执行上下文（Handoff）===
    'handoff': {
        'objective': str,             # 任务目标
        'context': str,               # 上下文（自动注入上游结果）
        'inputs': List[str],          # 需要提取的数据字段
        'instructions': List[str],    # 执行步骤
    },
}
```

## DAG 调度器实现

```python
from collections import defaultdict, deque
from typing import List, Dict
import asyncio


class DAGScheduler:
    def __init__(self, steps: List[Dict]):
        self.steps = {s['id']: s for s in steps}
        self.results = {}

    def topological_sort(self) -> List[List[str]]:
        """层级化拓扑排序：返回 [[level0_ids], [level1_ids], ...]"""
        dep_graph = {s['id']: s.get('deps', []) for s in self.steps.values()}
        in_degree = {sid: len(deps) for sid, deps in dep_graph.items()}
        reverse_graph = defaultdict(list)
        for sid, deps in dep_graph.items():
            for dep_id in deps:
                reverse_graph[dep_id].append(sid)

        levels = []
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        processed = set()

        while queue:
            current_level = list(queue)
            queue.clear()
            levels.append(current_level)

            for step_id in current_level:
                processed.add(step_id)
                for dependent in reverse_graph[step_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(processed) != len(self.steps):
            raise ValueError("检测到循环依赖")

        return levels

    async def execute(self) -> Dict:
        """层内并行、层间串行执行"""
        levels = self.topological_sort()

        for level_idx, level_ids in enumerate(levels):
            # 层内并行执行
            tasks = []
            for step_id in level_ids:
                step = self.inject_upstream_results(self.steps[step_id])
                tasks.append(self.execute_step(step))

            results = await asyncio.gather(*tasks)

            for step_id, result in zip(level_ids, results):
                self.results[step_id] = result

        return self.results

    def inject_upstream_results(self, step: Dict) -> Dict:
        """将上游任务结果自动注入到当前任务的 handoff.context"""
        for dep_id in step.get('deps', []):
            if dep_id in self.results:
                result = self.results[dep_id]
                context_snippet = f"【上游任务结果】ID: {dep_id}\n{result}"
                step.setdefault('handoff', {})
                step['handoff']['context'] = (
                    step['handoff'].get('context', '') + context_snippet
                )
        return step

    async def execute_step(self, step: Dict) -> Dict:
        """执行单个步骤（需实现）"""
        # TODO: 调用 Router 选择 Agent，获取 Lease，执行 AgentCall
        raise NotImplementedError
```

## 上下文自动注入

DAG 调度器自动将上游任务的执行结果注入到下游任务的上下文中：

```python
def inject_upstream_results(task: Dict) -> Dict:
    """将上游任务结果自动注入到当前任务的 handoff.context"""
    for dep_id in task.get('deps', []):
        if dep_id in task_results:
            result = task_results[dep_id]
            context_snippet = f"【上游任务结果】ID: {dep_id}\n{result}"
            task['handoff']['context'] += context_snippet
    return task
```

**优势**：
- 数据流自动化管理
- 任务间松耦合
- 执行逻辑与数据传递分离

## DAG 合法性验证

```python
def validate_dag(steps: List[Dict]) -> Dict:
    """验证 DAG 结构合法性"""
    task_ids = {s['id'] for s in steps}
    issues = []

    for step in steps:
        # 检查依赖存在性
        for dep_id in step.get('deps', []):
            if dep_id not in task_ids:
                issues.append(f"步骤 {step['id']} 依赖不存在的 {dep_id}")

        # 检查自依赖
        if step['id'] in step.get('deps', []):
            issues.append(f"步骤 {step['id']} 存在自依赖")

    # 检查循环依赖（通过拓扑排序）
    try:
        DAGScheduler(steps).topological_sort()
    except ValueError as e:
        issues.append(str(e))

    return {
        'valid': len(issues) == 0,
        'issues': issues,
    }
```

## 四种 DAG 依赖模式

### 1. 线性链

```
A → B → C
```

- **场景**：思维链推理、顺序审核
- **特点**：严格串行，无并行机会

### 2. 扇入（Fan-in）

```
A ─┐
B ─┼→ D
C ─┘
```

- **场景**：多源数据整合、综合评估
- **特点**：D 等待 A、B、C 全部完成

### 3. 扇出（Fan-out）

```
    ┌→ B
A ──┼→ C
    └→ D
```

- **场景**：并行分析、数据分发
- **特点**：B、C、D 可并行执行

### 4. 菱形（Diamond）

```
    ┌→ B ─┐
A ──┤     ├→ D
    └→ C ─┘
```

- **场景**：Map-Reduce、多工具并行后汇总
- **特点**：B、C 并行，D 等待 B、C

## 使用示例

```python
# 定义任务 DAG
steps = [
    {'id': 's1', 'deps': [], 'title': '获取用户列表'},
    {'id': 's2', 'deps': ['s1'], 'title': '提取用户详情 - 批次1'},
    {'id': 's3', 'deps': ['s1'], 'title': '提取用户详情 - 批次2'},
    {'id': 's4', 'deps': ['s1'], 'title': '提取用户详情 - 批次3'},
    {'id': 's5', 'deps': ['s2', 's3', 's4'], 'title': '合并结果'},
]

# 创建调度器
scheduler = DAGScheduler(steps)

# 拓扑排序
levels = scheduler.topological_sort()
# 结果: [['s1'], ['s2', 's3', 's4'], ['s5']]

# 执行
results = await scheduler.execute()
```
