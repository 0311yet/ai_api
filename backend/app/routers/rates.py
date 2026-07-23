"""费率管理路由

GET  /admin/rates                  - 列出所有 PoolItem 的费率（含 pool/provider 名）
PUT  /admin/rates/{item_id}        - 更新某个 PoolItem 的费率
PUT  /admin/rates/provider/{pid}   - 更新 Provider 的 is_paid 标记
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.middleware import verify_admin
from app.models import PoolItem, Pool, Provider
from app.schemas import PoolItemOut, PoolItemPriceUpdate, ProviderOut

router = APIRouter(prefix="/admin/rates", tags=["rates"], dependencies=[Depends(verify_admin)])


@router.get("", response_model=list[PoolItemOut])
async def list_rates(session: AsyncSession = Depends(get_session)):
    """列出所有 PoolItem 的费率，按 pool → priority 排序"""
    q = (
        select(PoolItem)
        .options(selectinload(PoolItem.pool), selectinload(PoolItem.provider))
        .join(Pool, PoolItem.pool_id == Pool.id)
        .order_by(Pool.id, PoolItem.priority, PoolItem.id)
    )
    result = await session.execute(q)
    items = result.scalars().all()

    out = []
    for item in items:
        d = PoolItemOut.model_validate(item).model_dump()
        d["provider_name"] = item.provider.name if item.provider else None
        out.append(PoolItemOut(**d))
    return out


@router.put("/{item_id}", response_model=PoolItemOut)
async def update_rate(
    item_id: int,
    data: PoolItemPriceUpdate,
    session: AsyncSession = Depends(get_session),
):
    """更新某个 PoolItem 的费率字段（只改提供的字段）"""
    item = (
        await session.execute(
            select(PoolItem)
            .options(selectinload(PoolItem.provider))
            .where(PoolItem.id == item_id)
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Pool item not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await session.commit()
    await session.refresh(item)

    d = PoolItemOut.model_validate(item).model_dump()
    d["provider_name"] = item.provider.name if item.provider else None
    return PoolItemOut(**d)


@router.put("/provider/{provider_id}", response_model=ProviderOut)
async def update_provider_paid(
    provider_id: int,
    is_paid: bool,
    session: AsyncSession = Depends(get_session),
):
    """更新 Provider 的 is_paid 标记（决定该 provider 按 free 还是 paid 价计费）"""
    provider = await session.get(Provider, provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    provider.is_paid = is_paid
    await session.commit()
    await session.refresh(provider)
    return provider
