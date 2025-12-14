"""
@PURPOSE: 定义执行证据契约，用于审计和回放
@OUTLINE:
    - enum EvidenceType: 证据类型 (screenshot/video/dom_snapshot等)
    - enum EvidenceStorage: 存储类型 (s3/local/inline)
    - class Evidence: 证据定义
    - class EvidenceCollection: 证据集合
    - class ReplayManifest: 回放清单
@GOTCHAS:
    - 所有执行类 Agent 必须收集证据
    - 证据有三层生命周期: hot(30天)/warm(90天)/cold(365天)
@DEPENDENCIES:
    - 外部: pydantic, datetime, enum
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceType(StrEnum):
    """证据类型"""

    SCREENSHOT = "screenshot"  # 截图
    VIDEO = "video"  # 视频录制
    DOM_SNAPSHOT = "dom_snapshot"  # DOM 快照
    NETWORK_HAR = "network_har"  # 网络日志 (HAR 格式)
    UI_TREE = "ui_tree"  # UI 控件树 (移动端)
    CONSOLE_LOG = "console_log"  # 控制台日志
    ACTION_LOG = "action_log"  # 操作日志
    FILE_ARTIFACT = "file_artifact"  # 文件工件
    CONTAINER_LOG = "container_log"  # 容器日志
    COMMAND_OUTPUT = "command_output"  # 命令输出


class EvidenceStorage(StrEnum):
    """证据存储类型"""

    S3 = "s3"  # AWS S3 / MinIO
    LOCAL = "local"  # 本地文件系统
    INLINE = "inline"  # 内联数据 (Base64)


class Evidence(BaseModel):
    """
    Evidence - 执行证据

    证据是执行结果的证明材料，用于：
    - 审计追踪
    - 回放重现
    - 问题诊断
    - Critic 验证

    Example:
        >>> evidence = Evidence(
        ...     id="ev_abc123",
        ...     type=EvidenceType.SCREENSHOT,
        ...     task_id="task_001",
        ...     step_id="step_001",
        ...     storage=EvidenceStorage.S3,
        ...     uri="s3://openmanus-evidence/task_001/screenshot_001.png",
        ...     content_type="image/png",
        ...     size_bytes=102400,
        ... )
    """

    # =========================================================================
    # 标识
    # =========================================================================
    id: str = Field(..., description="证据 ID，格式: ev_{uuid}")
    type: EvidenceType = Field(..., description="证据类型")

    # =========================================================================
    # 关联
    # =========================================================================
    task_id: str = Field(..., description="任务 ID")
    step_id: str = Field(..., description="步骤 ID")
    call_id: str | None = Field(default=None, description="调用 ID")

    # =========================================================================
    # 存储
    # =========================================================================
    storage: EvidenceStorage = Field(default=EvidenceStorage.S3)
    uri: str = Field(..., description="存储 URI")
    content_type: str = Field(default="application/octet-stream", description="MIME 类型")
    size_bytes: int = Field(default=0, ge=0, description="文件大小 (字节)")
    checksum: str | None = Field(default=None, description="SHA256 校验和")

    # =========================================================================
    # 内联数据 (小文件)
    # =========================================================================
    inline_data: str | None = Field(
        default=None,
        description="Base64 编码的内联数据 (仅 storage=inline 时)",
    )

    # =========================================================================
    # 时间
    # =========================================================================
    captured_at: datetime = Field(default_factory=datetime.utcnow, description="采集时间")
    expires_at: datetime | None = Field(default=None, description="过期时间")

    # =========================================================================
    # 上下文
    # =========================================================================
    description: str = Field(default="", description="描述")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="上下文信息: url, selector, action, etc.",
    )

    # =========================================================================
    # 元数据
    # =========================================================================
    metadata: dict[str, str] = Field(default_factory=dict)

    # =========================================================================
    # 生命周期层级
    # =========================================================================
    tier: str = Field(
        default="hot",
        description="存储层级: hot (30天), warm (90天), cold (365天)",
    )

    def is_expired(self) -> bool:
        """检查是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at

    def to_download_url(self, presign_seconds: int = 3600) -> str:
        """生成预签名下载 URL (需要后端实现)"""
        # 这里只是占位，实际实现在 EvidenceStore
        return self.uri


class EvidenceCollection(BaseModel):
    """证据集合 - 一个 Step 的所有证据"""

    step_id: str
    items: list[Evidence] = Field(default_factory=list)

    # 按类型索引
    screenshots: list[Evidence] = Field(default_factory=list)
    videos: list[Evidence] = Field(default_factory=list)
    dom_snapshots: list[Evidence] = Field(default_factory=list)
    action_logs: list[Evidence] = Field(default_factory=list)

    def add(self, evidence: Evidence) -> None:
        """添加证据"""
        self.items.append(evidence)
        match evidence.type:
            case EvidenceType.SCREENSHOT:
                self.screenshots.append(evidence)
            case EvidenceType.VIDEO:
                self.videos.append(evidence)
            case EvidenceType.DOM_SNAPSHOT:
                self.dom_snapshots.append(evidence)
            case EvidenceType.ACTION_LOG:
                self.action_logs.append(evidence)

    def get_by_type(self, evidence_type: EvidenceType) -> list[Evidence]:
        """按类型获取证据"""
        return [e for e in self.items if e.type == evidence_type]

    def total_size_bytes(self) -> int:
        """总大小"""
        return sum(e.size_bytes for e in self.items)


class ReplayManifest(BaseModel):
    """回放清单 - 用于重现执行过程"""

    task_id: str
    step_id: str

    # 回放入口
    replay_uri: str = Field(..., description="回放入口 URI")
    script_url: str | None = Field(default=None, description="可下载的回放脚本")

    # 工件列表
    artifacts: list[str] = Field(default_factory=list, description="相关工件 URI")

    # 操作序列
    actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="操作序列: [{action, selector, value, timestamp}, ...]",
    )

    # 时间线
    timeline: list[dict[str, Any]] = Field(
        default_factory=list,
        description="时间线: [{timestamp, event, data}, ...]",
    )

    # 格式版本
    format_version: str = Field(default="openmanus-replay-v1")

    # 生成时间
    generated_at: datetime = Field(default_factory=datetime.utcnow)
