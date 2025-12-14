"""
@PURPOSE: 定义平台通用类型别名，提高代码可读性和类型安全性
@OUTLINE:
    - ID 类型: TaskId, StepId, CallId, LeaseId, ResourceId, AgentId, TraceId, SpanId
    - JSON 类型: JsonValue, JsonDict, JsonList
    - 元数据类型: Metadata, Labels, Headers
    - 时间类型: Milliseconds, Seconds
    - 成本类型: USD, Tokens
@DEPENDENCIES:
    - 外部: typing (NewType, TypeAlias)
"""

from typing import Any, NewType, TypeAlias

# =============================================================================
# ID 类型 - 使用 NewType 确保类型安全
# =============================================================================

TaskId = NewType("TaskId", str)
"""任务 ID，格式: task_{uuid}"""

StepId = NewType("StepId", str)
"""步骤 ID，格式: step_{uuid}"""

CallId = NewType("CallId", str)
"""调用 ID，格式: call_{uuid}"""

LeaseId = NewType("LeaseId", str)
"""租约 ID，格式: lease_{uuid}"""

ResourceId = NewType("ResourceId", str)
"""资源 ID，格式: {type}_{uuid}"""

AgentId = NewType("AgentId", str)
"""Agent ID，格式: {domain}.{role}"""

TraceId = NewType("TraceId", str)
"""链路追踪 ID (OpenTelemetry)"""

SpanId = NewType("SpanId", str)
"""Span ID (OpenTelemetry)"""

# =============================================================================
# JSON 类型别名
# =============================================================================

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
"""JSON 兼容的值类型"""

JsonDict: TypeAlias = dict[str, Any]
"""JSON 对象类型"""

JsonList: TypeAlias = list[Any]
"""JSON 数组类型"""

# =============================================================================
# 回调类型别名
# =============================================================================

Metadata: TypeAlias = dict[str, str | int | float | bool]
"""元数据字典，值只能是基本类型"""

Labels: TypeAlias = dict[str, str]
"""标签字典，K8s 风格的 key-value 对"""

Headers: TypeAlias = dict[str, str]
"""HTTP 头字典"""

# =============================================================================
# 时间类型别名
# =============================================================================

Milliseconds = NewType("Milliseconds", int)
"""毫秒时间"""

Seconds = NewType("Seconds", float)
"""秒时间"""

# =============================================================================
# 成本类型别名
# =============================================================================

USD = NewType("USD", float)
"""美元金额"""

Tokens = NewType("Tokens", int)
"""Token 数量"""
