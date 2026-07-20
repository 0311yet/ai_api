"""管理接口 - 通道和密钥的CRUD"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import Channel, Key
from datetime import datetime

router = APIRouter(prefix="/admin")


@router.get("/channels")
async def list_channels(session: AsyncSession = Depends(get_session)):
    """列出所有通道"""
    stmt = (
        select(Channel)
        .options(selectinload(Channel.keys))
        .order_by(Channel.id)
    )
    result = await session.execute(stmt)
    channels = result.scalars().all()
    
    # 单查一次所有key的状态聚合，避免在循环里 len(ch.keys)
    out = []
    for ch in channels:
        keys = ch.keys
        out.append({
            "id": ch.id,
            "name": ch.name,
            "display_name": ch.display_name,
            "provider": ch.provider,
            "base_url": ch.base_url,
            "models": ch.models or [],
            "is_active": ch.is_active,
            "is_default": ch.is_default,
            "keys_count": len(keys),
            "active_keys": sum(1 for k in keys if k.is_active and not k.is_blocked),
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
        })
    return {"channels": out}


@router.post("/channels")
async def create_channel(
    name: str = Body(...),
    display_name: Optional[str] = Body(None),
    provider: str = Body(...),  # openai/anthropic/google/local
    base_url: str = Body(...),
    models: list = Body(...),
    is_default: bool = Body(False),
    session: AsyncSession = Depends(get_session),
):
    """创建通道"""
    ch = Channel(
        name=name,
        display_name=display_name or name,
        provider=provider,
        base_url=base_url,
        models=models,
        is_default=is_default,
    )
    session.add(ch)
    await session.commit()
    return {"id": ch.id, "message": "Created"}


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    name: Optional[str] = Body(None),
    display_name: Optional[str] = Body(None),
    provider: Optional[str] = Body(None),
    base_url: Optional[str] = Body(None),
    models: Optional[list] = Body(None),
    is_active: Optional[bool] = Body(None),
    is_default: Optional[bool] = Body(None),
    session: AsyncSession = Depends(get_session),
):
    """更新通道"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await session.execute(stmt)
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(404, "Channel not found")
    
    if name is not None: ch.name = name
    if display_name is not None: ch.display_name = display_name
    if provider is not None: ch.provider = provider
    if base_url is not None: ch.base_url = base_url
    if models is not None: ch.models = models
    if is_active is not None: ch.is_active = is_active
    if is_default is not None: ch.is_default = is_default
    ch.updated_at = datetime.utcnow()
    
    await session.commit()
    return {"message": "Updated"}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, session: AsyncSession = Depends(get_session)):
    """删除通道"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await session.execute(stmt)
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(404, "Channel not found")
    
    await session.delete(ch)
    await session.commit()
    return {"message": "Deleted"}


# 密钥管理
@router.get("/channels/{channel_id}/keys")
async def list_keys(channel_id: int, session: AsyncSession = Depends(get_session)):
    """列出通道下的密钥"""
    stmt = select(Key).where(Key.channel_id == channel_id)
    result = await session.execute(stmt)
    keys = result.scalars().all()
    
    return {"keys": [
        {
            "id": k.id,
            "name": k.name,
            "key_preview": k.key_value[:8] + "..." + k.key_value[-4:] if len(k.key_value) > 12 else "***",
            "is_active": k.is_active,
            "is_blocked": k.is_blocked,
            "weight": k.weight,
            "request_count": k.request_count,
            "error_count": k.error_count,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "last_error": (k.last_error[:200] if k.last_error else None),
        }
        for k in keys
    ]}


@router.post("/channels/{channel_id}/keys")
async def create_key(
    channel_id: int,
    key_value: str = Body(...),
    name: Optional[str] = Body(None),
    weight: int = Body(1),
    session: AsyncSession = Depends(get_session),
):
    """添加密钥"""
    key = Key(
        channel_id=channel_id,
        key_value=key_value,
        name=name,
        weight=weight,
    )
    session.add(key)
    await session.commit()
    return {"id": key.id, "message": "Created"}


@router.put("/keys/{key_id}")
async def update_key(
    key_id: int,
    is_active: Optional[bool] = Body(None),
    is_blocked: Optional[bool] = Body(None),
    weight: Optional[int] = Body(None),
    name: Optional[str] = Body(None),
    session: AsyncSession = Depends(get_session),
):
    """更新密钥"""
    stmt = select(Key).where(Key.id == key_id)
    result = await session.execute(stmt)
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    
    if is_active is not None: key.is_active = is_active
    if is_blocked is not None: key.is_blocked = is_blocked
    if weight is not None: key.weight = weight
    if name is not None: key.name = name
    
    await session.commit()
    return {"message": "Updated"}


@router.delete("/keys/{key_id}")
async def delete_key(key_id: int, session: AsyncSession = Depends(get_session)):
    """删除密钥"""
    stmt = select(Key).where(Key.id == key_id)
    result = await session.execute(stmt)
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    
    await session.delete(key)
    await session.commit()
    return {"message": "Deleted"}