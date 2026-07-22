"""应用配置 - 支持环境变量覆盖"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 服务
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_gateway.db"

    # 管理后台密码（单密码登录）
    ADMIN_PASSWORD: str = "admin123"

    # 客户端 key 鉴权的 header
    # 客户端调用 /v1/* 时用 Authorization: Bearer sk-xxx

    # 上游请求超时（秒）
    UPSTREAM_TIMEOUT: float = 120.0

    # 日志清理：保留天数
    LOG_RETENTION_DAYS: int = 30

    # 聚合任务：周期（秒）
    AGGREGATION_INTERVAL: int = 300  # 5 分钟
    CLEANUP_INTERVAL: int = 3600      # 1 小时


settings = Settings()
