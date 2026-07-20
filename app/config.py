"""配置"""
import os

# 服务配置
HOST = "0.0.0.0"
PORT = 8080
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# 数据库
DATABASE_URL = "sqlite+aiosqlite:///./ai_gateway.db"

# 日志保留天数
LOG_RETENTION_DAYS = 30

# 请求超时(秒)
REQUEST_TIMEOUT = 120

# 密钥池
KEY_POOL_STRATEGY = "round_robin"  # round_robin / random / priority

# API密钥(管理界面)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "sk-admin-123456")

# CORS
ALLOWED_ORIGINS = ["*"]