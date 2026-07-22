"""鉴权中间件

两种鉴权：
1. Admin 鉴权：调用 /admin/* 需要 X-Admin-Key header
2. Client 鉴权：调用 /v1/* 需要 Authorization: Bearer sk-xxx
"""
from fastapi import Request, HTTPException, Security, Header
from fastapi.security import APIKeyHeader

from app.config import settings

# Header 定义（用于 OpenAPI 文档 + Security 依赖）
admin_key_scheme = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def verify_admin(x_admin_key: str = Security(admin_key_scheme)):
    """管理后台鉴权：校验 X-Admin-Key == ADMIN_PASSWORD"""
    if not x_admin_key or x_admin_key != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return x_admin_key


async def get_admin_key_optional(x_admin_key: str = Security(admin_key_scheme)):
    """可选 admin key（登录验证用）"""
    return x_admin_key
