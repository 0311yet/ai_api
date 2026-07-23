"""Platform + PlatformKey CRUD 路由

Platform: 上游 AI 模型厂商（如 NVIDIA NIM, Google, Groq）
PlatformKey: 平台 API 密钥（一个 Platform 可有多个 Keys，支持负载均衡和回退）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.middleware import verify_admin
from app.models import Platform, PlatformKey, PoolItem
from app.schemas import (
    PlatformCreate, PlatformUpdate, PlatformOut, PlatformDetailOut,
    PlatformKeyCreate, PlatformKeyUpdate, PlatformKeyOut,
)

router = APIRouter(
    prefix="/admin/platforms",
    tags=["platforms"],
    dependencies=[Depends(verify_admin)],
)


# ── Platform CRUD ──────────────────────────────────────────────

@router.get("", response_model=list[PlatformOut])
async def list_platforms(session: AsyncSession = Depends(get_session)):
    """列出所有 Platforms（含 Keys）"""
    q = select(Platform).options(selectinload(Platform.platform_keys)).order_by(Platform.name)
    result = await session.execute(q)
    platforms = result.scalars().all()
    
    # 手动构造 PlatformOut 以包含 platform_keys
    return [
        PlatformOut(
            id=p.id,
            name=p.name,
            base_url=p.base_url,
            models=p.models,
            is_paid=p.is_paid,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
            platform_keys=[PlatformKeyOut.model_validate(k) for k in p.platform_keys],
        )
        for p in platforms
    ]


@router.post("", response_model=PlatformOut, status_code=201)
async def create_platform(data: PlatformCreate, session: AsyncSession = Depends(get_session)):
    """创建 Platform"""
    exists = await session.execute(select(Platform).where(Platform.name == data.name))
    if exists.scalar_one_or_none():
        raise HTTPException(400, f"Platform '{data.name}' already exists")

    platform = Platform(
        name=data.name,
        base_url=data.base_url,
        models=data.models,
        is_paid=data.is_paid,
        is_active=data.is_active,
    )
    session.add(platform)
    await session.commit()
    await session.refresh(platform)
    return platform


@router.get("/{platform_id}", response_model=PlatformDetailOut)
async def get_platform(platform_id: int, session: AsyncSession = Depends(get_session)):
    """获取 Platform 详情（含 Keys）"""
    result = await session.execute(
        select(Platform)
        .options(selectinload(Platform.platform_keys))
        .where(Platform.id == platform_id)
    )
    platform = result.scalar_one_or_none()
    if not platform:
        raise HTTPException(404, "Platform not found")
    return platform


@router.put("/{platform_id}", response_model=PlatformOut)
async def update_platform(
    platform_id: int,
    data: PlatformUpdate,
    session: AsyncSession = Depends(get_session),
):
    """更新 Platform"""
    platform = await session.get(Platform, platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(platform, k, v)
    await session.commit()
    await session.refresh(platform)
    return platform


@router.delete("/{platform_id}")
async def delete_platform(platform_id: int, session: AsyncSession = Depends(get_session)):
    """删除 Platform（同时删除所有关联的 PlatformKeys）"""
    platform = await session.get(Platform, platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")

    # 检查是否有关联的 PoolItems
    items_result = await session.execute(
        select(PoolItem).where(PoolItem.platform_id == platform_id)
    )
    has_items = items_result.scalar_one_or_none()
    if has_items:
        raise HTTPException(
            400,
            "Cannot delete platform: it has associated pool items. "
            "Please remove them first or migrate to another platform."
        )

    await session.delete(platform)
    await session.commit()
    return {"message": "deleted"}


# ── PlatformKey CRUD ────────────────────────────────────────────

@router.get("/{platform_id}/keys", response_model=list[PlatformKeyOut])
async def list_platform_keys(
    platform_id: int,
    session: AsyncSession = Depends(get_session),
):
    """列出 Platform 下的所有 Keys"""
    platform = await session.get(Platform, platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")

    result = await session.execute(
        select(PlatformKey)
        .where(PlatformKey.platform_id == platform_id)
        .order_by(PlatformKey.id)
    )
    return result.scalars().all()


@router.post("/{platform_id}/keys", response_model=PlatformKeyOut, status_code=201)
async def create_platform_key(
    platform_id: int,
    data: PlatformKeyCreate,
    session: AsyncSession = Depends(get_session),
):
    """为 Platform 添加一个 Key"""
    platform = await session.get(Platform, platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")

    # 检查同一 platform 下 api_key 是否重复
    exists = await session.execute(
        select(PlatformKey).where(
            PlatformKey.platform_id == platform_id,
            PlatformKey.api_key == data.api_key,
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(400, "This API key already exists for this platform")

    key = PlatformKey(
        platform_id=platform_id,
        api_key=data.api_key,
        label=data.label,
        enabled=data.enabled,
        is_active=True,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key


@router.put("/{platform_id}/keys/{key_id}", response_model=PlatformKeyOut)
async def update_platform_key(
    platform_id: int,
    key_id: int,
    data: PlatformKeyUpdate,
    session: AsyncSession = Depends(get_session),
):
    """更新 PlatformKey"""
    key = await session.get(PlatformKey, key_id)
    if not key or key.platform_id != platform_id:
        raise HTTPException(404, "PlatformKey not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(key, k, v)
    await session.commit()
    await session.refresh(key)
    return key


@router.delete("/{platform_id}/keys/{key_id}")
async def delete_platform_key(
    platform_id: int,
    key_id: int,
    session: AsyncSession = Depends(get_session),
):
    """删除 PlatformKey"""
    key = await session.get(PlatformKey, key_id)
    if not key or key.platform_id != platform_id:
        raise HTTPException(404, "PlatformKey not found")
    await session.delete(key)
    await session.commit()
    return {"message": "deleted"}