"""Pool CRUD 路由（含 PoolItem 子表）- 支持 Provider(兼容) 和 Platform(新)

PoolItem 现在优先使用 platform_id，provider_id 保留用于向后兼容迁移期。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.middleware import verify_admin
from app.models import Pool, PoolItem, Provider, Platform
from app.schemas import (
    PoolCreate, PoolUpdate, PoolOut,
    PoolItemCreate, PoolItemOut,
)

router = APIRouter(prefix="/admin/pools", tags=["pools"], dependencies=[Depends(verify_admin)])


async def _load_pool_with_items(session, pool_id) -> Pool:
    """加载 pool + 它的 items + 每个 item 关联的 provider/platform"""
    q = (
        select(Pool)
        .options(
            selectinload(Pool.pool_items).selectinload(PoolItem.provider),
            selectinload(Pool.pool_items).selectinload(PoolItem.platform),
        )
        .where(Pool.id == pool_id)
    )
    pool = (await session.execute(q)).scalar_one_or_none()
    return pool


def _pool_to_out(pool: Pool) -> PoolOut:
    """转换 model -> response schema，附加 platform_name / provider_name"""
    items = []
    for item in pool.pool_items:
        item_dict = PoolItemOut.model_validate(item).model_dump()
        # 优先用 platform_name（新的），兼容 provider_name（旧的）
        item_dict["platform_name"] = (
            item.platform.name if item.platform else None
        )
        item_dict["provider_name"] = (
            item.provider.name if item.provider else None
        )
        items.append(PoolItemOut(**item_dict))
    return PoolOut(
        id=pool.id,
        name=pool.name,
        display_name=pool.display_name,
        strategy=pool.strategy,
        is_active=pool.is_active,
        created_at=pool.created_at,
        items=items,
    )


async def _resolve_item_target(session, data: PoolItemCreate) -> tuple:
    """
    解析 PoolItemCreate 中的 target（platform_id 或 provider_id）。
    返回 (platform_id, provider_id) 元组。

    优先级：
    1. platform_id 非空 → 使用 platform_id
    2. provider_id 非空 → 使用 provider_id（向后兼容）
    """
    platform_id = data.platform_id
    provider_id = data.provider_id

    if platform_id:
        platform = await session.get(Platform, platform_id)
        if not platform:
            raise HTTPException(400, f"Platform {platform_id} not found")
        # provider_id 用于兼容旧数据（如有）
        return platform_id, provider_id

    if provider_id:
        provider = await session.get(Provider, provider_id)
        if not provider:
            raise HTTPException(400, f"Provider {provider_id} not found")
        return platform_id, provider_id

    raise HTTPException(400, "Either platform_id or provider_id must be provided")


@router.get("", response_model=list[PoolOut])
async def list_pools(session: AsyncSession = Depends(get_session)):
    q = select(Pool).options(
        selectinload(Pool.pool_items).selectinload(PoolItem.provider),
        selectinload(Pool.pool_items).selectinload(PoolItem.platform),
    ).order_by(Pool.id)
    result = await session.execute(q)
    pools = result.scalars().all()
    return [_pool_to_out(p) for p in pools]


@router.post("", response_model=PoolOut, status_code=201)
async def create_pool(data: PoolCreate, session: AsyncSession = Depends(get_session)):
    # 检查 name 唯一
    exists = await session.execute(select(Pool).where(Pool.name == data.name))
    if exists.scalar_one_or_none():
        raise HTTPException(400, f"Pool name '{data.name}' already exists")

    pool = Pool(
        name=data.name,
        display_name=data.display_name,
        strategy=data.strategy,
        is_active=data.is_active,
    )
    session.add(pool)
    await session.flush()  # 拿 pool.id

    # 创建 PoolItem
    for item_data in data.items:
        platform_id, provider_id = await _resolve_item_target(session, item_data)
        item = PoolItem(
            pool_id=pool.id,
            platform_id=platform_id,
            provider_id=provider_id,
            platform_key_id=item_data.platform_key_id,
            key_label=item_data.key_label,
            model=item_data.model,
            priority=item_data.priority,
            weight=item_data.weight,
            is_active=item_data.is_active,
        )
        session.add(item)

    await session.commit()
    pool = await _load_pool_with_items(session, pool.id)
    return _pool_to_out(pool)


@router.get("/{pool_id}", response_model=PoolOut)
async def get_pool(pool_id: int, session: AsyncSession = Depends(get_session)):
    pool = await _load_pool_with_items(session, pool_id)
    if not pool:
        raise HTTPException(404, "Pool not found")
    return _pool_to_out(pool)


@router.put("/{pool_id}", response_model=PoolOut)
async def update_pool(
    pool_id: int,
    data: PoolUpdate,
    session: AsyncSession = Depends(get_session),
):
    pool = await session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "Pool not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(pool, k, v)
    await session.commit()
    pool = await _load_pool_with_items(session, pool_id)
    return _pool_to_out(pool)


@router.delete("/{pool_id}")
async def delete_pool(pool_id: int, session: AsyncSession = Depends(get_session)):
    pool = await session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "Pool not found")
    await session.delete(pool)
    await session.commit()
    return {"message": "deleted"}


# ---------- PoolItem 管理：增加/删除/修改池内模型 ----------

@router.post("/{pool_id}/items", response_model=PoolOut, status_code=201)
async def add_pool_item(
    pool_id: int,
    data: PoolItemCreate,
    session: AsyncSession = Depends(get_session),
):
    pool = await session.get(Pool, pool_id)
    if not pool:
        raise HTTPException(404, "Pool not found")

    platform_id, provider_id = await _resolve_item_target(session, data)

    item = PoolItem(
        pool_id=pool_id,
        platform_id=platform_id,
        provider_id=provider_id,
        platform_key_id=data.platform_key_id,
        key_label=data.key_label,
        model=data.model,
        priority=data.priority,
        weight=data.weight,
        is_active=data.is_active,
    )
    session.add(item)
    await session.commit()
    pool = await _load_pool_with_items(session, pool_id)
    return _pool_to_out(pool)


@router.delete("/{pool_id}/items/{item_id}")
async def delete_pool_item(
    pool_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(PoolItem, item_id)
    if not item or item.pool_id != pool_id:
        raise HTTPException(404, "Pool item not found")
    await session.delete(item)
    await session.commit()
    return {"message": "deleted"}


@router.put("/{pool_id}/items/{item_id}", response_model=PoolOut)
async def update_pool_item(
    pool_id: int,
    item_id: int,
    data: PoolItemCreate,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(PoolItem, item_id)
    if not item or item.pool_id != pool_id:
        raise HTTPException(404, "Pool item not found")

    platform_id, provider_id = await _resolve_item_target(session, data)

    item.platform_id = platform_id
    item.provider_id = provider_id
    item.model = data.model
    item.priority = data.priority
    item.weight = data.weight
    item.is_active = data.is_active
    await session.commit()
    pool = await _load_pool_with_items(session, pool_id)
    return _pool_to_out(pool)