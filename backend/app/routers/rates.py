"""费率管理路由

GET  /admin/rates                  - 列出所有 PoolItem 的费率（含 pool/provider 名）
PUT  /admin/rates/{item_id}        - 更新某个 PoolItem 的费率
PUT  /admin/rates/provider/{pid}   - 更新 Provider 的 is_paid 标记
GET  /admin/rates/models           - 按模型去重列出费率（从所有 Platform.models 汇总）
PUT  /admin/rates/models/{model}   - 更新某模型在所有 PoolItem 中的费率
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.middleware import verify_admin
from app.models import PoolItem, Pool, Provider, Platform
from app.schemas import PoolItemOut, PoolItemPriceUpdate, ProviderOut, ModelRateOut, ModelRateUpdate

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


@router.get("/models", response_model=list[ModelRateOut])
async def list_model_rates(session: AsyncSession = Depends(get_session)):
    """按模型去重列出费率。

    Sources: all Platform.models (JSON list) collected and deduplicated.
    For each model, find a PoolItem with that model to get current price.
    Returns one row per unique model name.
    """
    # 1. Collect all model names from all Platforms
    result = await session.execute(select(Platform.models, Platform.is_paid))
    all_models: dict[str, bool] = {}  # model_name -> in_any_paid_platform
    for models_json, is_paid in result:
        for m in (models_json or []):
            if m not in all_models:
                all_models[m] = False
            if is_paid:
                all_models[m] = True

    # 2. Get all PoolItems to find prices per model
    items_result = await session.execute(select(PoolItem))
    items = items_result.scalars().all()
    # model -> first PoolItem's prices (representative)
    model_prices: dict[str, dict] = {}
    in_pool: set[str] = set()
    for item in items:
        in_pool.add(item.model)
        if item.model not in model_prices:
            model_prices[item.model] = {
                "input_price": item.free_input_price or item.paid_input_price or 0,
                "output_price": item.free_output_price or item.paid_output_price or 0,
            }

    # 3. Build output: all models from platforms, with price (0 if not in pool)
    out = []
    for model_name in sorted(all_models.keys()):
        prices = model_prices.get(model_name, {"input_price": 0, "output_price": 0})
        out.append(ModelRateOut(
            model=model_name,
            input_price=prices["input_price"],
            output_price=prices["output_price"],
            in_pool=model_name in in_pool,
            is_paid=all_models[model_name],
        ))
    return out


@router.put("/models/{model}", response_model=ModelRateOut)
async def update_model_rate(
    model: str,
    data: ModelRateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update price for a model across ALL PoolItems that use it.

    Sets both free_* and paid_* to the same value (rough cost tracking).
    """
    result = await session.execute(select(PoolItem).where(PoolItem.model == model))
    items = result.scalars().all()
    if not items:
        raise HTTPException(404, f"No pool items found for model '{model}'")

    for item in items:
        item.free_input_price = data.input_price
        item.free_output_price = data.output_price
        item.paid_input_price = data.input_price
        item.paid_output_price = data.output_price
    await session.commit()

    return ModelRateOut(
        model=model,
        input_price=data.input_price,
        output_price=data.output_price,
        in_pool=True,
        is_paid=False,
    )
