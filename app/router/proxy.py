"""转发路由 - 兼容OpenAI格式"""
import time
from fastapi import APIRouter, Request, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.core.gateway import Gateway
from app.models import RequestLog
from app.config import ADMIN_API_KEY

router = APIRouter()


def verify_api_key(authorization: str = Header(None), x_api_key: str = Header(None, alias="x-api-key")):
    """验证API密钥（暂用admin key，后续可重构为独立用户系统）"""
    key = None
    if authorization and authorization.startswith("Bearer "):
        key = authorization[7:]
    elif x_api_key:
        key = x_api_key
    # 暂时允许任何API密钥访问，方便测试
    # TODO: 接入API密钥系统
    return key


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, session: AsyncSession = Depends(get_session)):
    """OpenAI兼容的chat completions"""
    gateway = Gateway(session)
    return await gateway.handle_chat_completion(request)


@router.get("/v1/models")
async def list_models(session: AsyncSession = Depends(get_session)):
    """列出可用模型 (OpenAI兼容)"""
    from sqlalchemy import select
    from app.models import Channel
    
    stmt = select(Channel).where(Channel.is_active == True)
    result = await session.execute(stmt)
    channels = result.scalars().all()
    
    models = []
    seen = set()
    for ch in channels:
        if ch.models:
            for m in ch.models:
                if m not in seen:
                    models.append({"id": m, "object": "model", "owned_by": ch.provider})
                    seen.add(m)
    
    return {"object": "list", "data": models}