"""Pool CRUD 路由（含 PoolItem 子表）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.middleware import verify_admin
from app.models import Pool, PoolItem, Provider
from app.schemas import (
    PoolCreate, PoolUpdate, PoolOut,
    PoolItemCreate, PoolItemOut,
)

router = APIRouter(prefix="/admin/pools", tags=["pools"], dependencies=[Depends(verify_admin)])


async def _load_pool_with_items(session, pool_id) -> Pool:
    """加载 pool + 它的 items + 每个 item 关联的 provider"""
    q = (
        select(Pool)
        .options(selectinload(Pool.pool_items).selectinload(PoolItem.provider))
        .where(Pool.id == pool_id)
    )
    pool = (await session.execute(q)).scalar_one_or_none()
    return pool


def _pool_to_out(pool: Pool) -> PoolOut:
    """转换 model -> response schema，附加 provider_name"""
    items = []
    for item in pool.pool_items:
        item_dict = PoolItemOut.model_validate(item).model_dump()
        item_dict["provider_name"] = item.provider.name if item.provider else None
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


@router.get("", response_model=list[PoolOut])
async def list_pools(session: AsyncSession = Depends(get_session)):
    q = select(Pool).options(
        selectinload(Pool.pool_items).selectinload(PoolItem.provider)
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
        provider = await session.get(Provider, item_data.provider_id)
        if not provider:
            raise HTTPException(400, f"Provider {item_data.provider_id} not found")
        item = PoolItem(
            pool_id=pool.id,
            provider_id=item_data.provider_id,
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
    provider = await session.get(Provider, data.provider_id)
    if not provider:
        raise HTTPException(400, f"Provider {data.provider_id} not found")

    item = PoolItem(
        pool_id=pool_id,
        provider_id=data.provider_id,
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
    item.provider_id = data.provider_id
    item.model = data.model
    item.priority = data.priority
    item.weight = data.weight
    item.is_active = data.is_active
    await session.commit()
    pool = await _load_pool_with_items(session, pool_id)
    return _pool_to_out(pool)
