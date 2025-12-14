"""
@PURPOSE: 实现应用配置
@OUTLINE:
    - class Settings: 应用配置
        - 数据库配置
        - LLM 配置
        - 资源配置
        - 可观测性配置
@GOTCHAS:
    - 支持环境变量覆盖
    - 支持 .env 文件
@DEPENDENCIES:
    - 外部: pydantic-settings
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """数据库配置"""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    name: str = Field(default="openmanus")
    user: str = Field(default="postgres")
    password: str = Field(default="")

    @property
    def url(self) -> str:
        """数据库连接 URL"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis 配置"""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: str = Field(default="")

    @property
    def url(self) -> str:
        """Redis 连接 URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class LLMSettings(BaseSettings):
    """
    LLM 配置

    支持通过环境变量或 .env 文件配置。
    环境变量前缀为 LLM_，例如 LLM_DEFAULT_MODEL=gpt-4。

    Example:
        >>> settings = LLMSettings()
        >>> settings.default_model
        'gpt-4'
    """

    model_config = SettingsConfigDict(env_prefix="LLM_")

    # === 基础配置 ===
    default_model: str = Field(default="gpt-4", description="默认模型")
    default_temperature: float = Field(default=0.7, ge=0, le=2, description="默认温度")
    default_max_tokens: int = Field(default=4096, ge=1, description="默认最大 Token")
    timeout_seconds: int = Field(default=60, ge=1, description="请求超时时间(秒)")

    # === API Keys ===
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_api_base: str = Field(default="", description="OpenAI API Base URL")
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
    deepseek_api_key: str = Field(default="", description="DeepSeek API Key")
    deepseek_api_base: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API Base URL",
    )

    # === 重试配置 ===
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    retry_min_wait: float = Field(default=1.0, ge=0, description="最小重试等待时间(秒)")
    retry_max_wait: float = Field(default=60.0, ge=1, description="最大重试等待时间(秒)")

    # === 速率限制 ===
    rate_limit_enabled: bool = Field(default=True, description="是否启用速率限制")
    default_rpm: int = Field(default=60, ge=1, description="每分钟请求数限制")
    default_tpm: int = Field(default=100000, ge=1, description="每分钟 Token 限制")

    # === 缓存配置 ===
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl_seconds: int = Field(default=3600, ge=0, description="缓存 TTL(秒)")

    # === Router/降级配置 ===
    router_enabled: bool = Field(default=True, description="是否启用 Router")
    routing_strategy: str = Field(
        default="simple-shuffle",
        description="路由策略: simple-shuffle, latency-based-routing, cost-based-routing",
    )
    fallback_models: list[str] = Field(
        default_factory=lambda: ["gpt-3.5-turbo", "claude-3-haiku-20240307"],
        description="降级模型列表",
    )

    # === 可观测性 ===
    tracing_enabled: bool = Field(default=True, description="是否启用 OTel 追踪")
    log_requests: bool = Field(default=False, description="是否记录请求内容")
    log_responses: bool = Field(default=False, description="是否记录响应内容")

    # === 成本控制 ===
    budget_usd: float | None = Field(default=None, description="预算上限(USD)")
    cost_tracking_enabled: bool = Field(default=True, description="是否启用成本追踪")


class ResourceSettings(BaseSettings):
    """资源配置"""

    model_config = SettingsConfigDict(env_prefix="RESOURCE_")

    browser_pool_size: int = Field(default=5)
    mobile_pool_size: int = Field(default=3)
    container_pool_size: int = Field(default=10)
    default_lease_ttl_seconds: int = Field(default=300)


class ObservabilitySettings(BaseSettings):
    """可观测性配置"""

    model_config = SettingsConfigDict(env_prefix="OTEL_")

    enabled: bool = Field(default=True)
    service_name: str = Field(default="openmanus")
    jaeger_endpoint: str = Field(default="http://localhost:14268/api/traces")
    prometheus_port: int = Field(default=9090)
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False)


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用信息
    app_name: str = Field(default="openmanus")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)

    # API 配置
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_prefix: str = Field(default="/api/v1")

    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    resource: ResourceSettings = Field(default_factory=ResourceSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)


# 全局配置实例
_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局配置"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def override_settings(settings: Settings) -> None:
    """覆盖全局配置 (测试用)"""
    global _settings
    _settings = settings
