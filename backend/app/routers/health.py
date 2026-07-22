"""Provider Health 管理接口

GET /admin/health/overview          - Provider 健康总览
GET /admin/health/rate-limit/<id>    - 单个 Provider 限流详情
"""
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Pool, PoolItem, Provider
from app.schemas import ProviderHealthItem, RateLimitWindow, PoolHealthOut, HealthOverview
from app.services import provider_health as ph

router = APIRouter(prefix="/admin/health", tags=["health"])


@router.get("/overview", response_model=HealthOverview)
async def health_overview(session: AsyncSession = Depends(get_session)):
    """
    返回所有 Pool 的 Provider 健康状态：
    - 滑动窗口用量（RPM/RPD/TPM/TPD）
    - 冷却状态（是否在冷却中、剩余时间、strike 次数）
    - 惩罚分
    - 有效优先级
    """
    result = await session.execute(
        select(Pool).where(Pool.is_active == True).order_by(Pool.name)
    )
    pools = result.scalars().all()
    out_pools = []

    for pool in pools:
        items_result = await session.execute(
            select(PoolItem, Provider)
            .join(Provider, PoolItem.provider_id == Provider.id)
            .where(PoolItem.pool_id == pool.id, PoolItem.is_active == True)
            .order_by(PoolItem.priority)
        )
        rows = items_result.all()
        providers = []

        for pool_item, provider in rows:
            state = ph.get_provider_state(provider.id)
            if state is None:
                state = ph.ProviderState(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    base_url=provider.base_url,
                    is_active=provider.is_active,
                    base_priority=pool_item.priority,
                )
                ph.register_provider(state)

            win = state.get_window(pool_item.model)
            rate_window = RateLimitWindow(
                rpm=win.count(60),
                rpd=win.count(86400),
                tpm=win.tokens(60),
                tpd=win.tokens(86400),
            )
            cooldown_until = None
            if state.cooldown_until and state.cooldown_until > time.time():
                cooldown_until = datetime.fromtimestamp(state.cooldown_until, tz=timezone.utc).isoformat()

            providers.append(ProviderHealthItem(
                provider_id=provider.id,
                provider_name=provider.name,
                base_url=provider.base_url,
                is_active=provider.is_active,
                model=pool_item.model or None,
                rate_window=rate_window,
                cooldown_until=cooldown_until,
                strike_count=state.strike_count,
                penalty_score=state.penalty_score,
                effective_priority=pool_item.priority - state.penalty_score,
            ))

        out_pools.append(PoolHealthOut(
            pool_id=pool.id,
            pool_name=pool.name,
            strategy=pool.strategy,
            providers=providers,
        ))

    return HealthOverview(
        pools=out_pools,
        sticky_sessions_active=ph.StickySessionManager_instance.count(),
    )


@router.get("/rate-limit/{provider_id}")
async def provider_rate_limit(
    provider_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    返回单个 Provider 的详细限流状态：
    - 各模型的滑动窗口用量
    - 当前冷却状态
    - 惩罚分
    """
    result = await session.execute(
        select(Provider).where(Provider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        return {"error": "Provider not found"}

    state = ph.get_provider_state(provider_id)
    if state is None:
        state = ph.ProviderState(
            provider_id=provider.id,
            provider_name=provider.name,
            base_url=provider.base_url,
            is_active=provider.is_active,
            base_priority=0,
        )
        ph.register_provider(state)

    windows = {}
    for model, win in state.windows.items():
        windows[model or "(default)"] = {
            "rpm": win.count(60),
            "rpd": win.count(86400),
            "tpm": win.tokens(60),
            "tpd": win.tokens(86400),
        }

    if state.cooldown_until and state.cooldown_until > time.time():
        cooldown_until = datetime.fromtimestamp(state.cooldown_until, tz=timezone.utc).isoformat()
    else:
        cooldown_until = None

    return {
        "provider_id": provider_id,
        "provider_name": provider.name,
        "is_active": provider.is_active,
        "penalty_score": state.penalty_score,
        "strike_count": state.strike_count,
        "cooldown_until": cooldown_until,
        "cooldown_remaining_s": round(state.cooldown_remaining(), 1),
        "effective_priority_reduction": state.penalty_score,
        "model_windows": windows,
        "sticky_model": state.sticky_model,
    }