"""登录验证路由：校验 admin key"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.middleware import get_admin_key_optional

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    ok: bool
    admin_key: str = ""


@router.post("/admin/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    """登录：密码正确返回 admin key（用于前端存 localStorage + 后续 X-Admin-Key header）"""
    if data.password == settings.ADMIN_PASSWORD:
        return LoginResponse(ok=True, admin_key=settings.ADMIN_PASSWORD)
    return LoginResponse(ok=False, admin_key="")


@router.get("/admin/verify", response_model=LoginResponse)
async def verify(admin_key: str = Depends(get_admin_key_optional)):
    """校验已存的 admin key 是否有效（前端启动时调用）"""
    if admin_key == settings.ADMIN_PASSWORD:
        return LoginResponse(ok=True, admin_key=admin_key)
    return LoginResponse(ok=False)
