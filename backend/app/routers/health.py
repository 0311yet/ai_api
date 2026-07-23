"""
PlatformKey Health 管理接口

GET /admin/health/overview          - 所有 Pool 的 PlatformKey 健康总览
GET /admin/health/rate-limit/<id>    - 单个 PlatformKey 限流详情

重构说明 (v1.3):
- 从 per-Provider 健康状态 → per-PlatformKey 健康状态
- PoolItem 的 health 状态现在归到其关联的 PlatformKey
- 同一个 PoolItem 的不同 Keys 显示为多个条目（支持多 Key 负载均衡展示）
"""
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Pool, PoolItem, Platform, PlatformKey
from app.schemas import ProviderHealthItem, RateLimitWindow, PoolHealthOut, HealthOverview
from app.services import provider_health as ph

router = APIRouter(prefix="/admin/health", tags=["health"])


@router.get("/overview", response_model=HealthOverview)
async def health_overview(session: AsyncSession = Depends(get_session)):
    """
    返回所有 Pool 的 PlatformKey 健康状态：
    - 每个 PoolItem × PlatformKey 组合一条（展示所有 keys 的健康状态）
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
        # 查询 PoolItem + Platform + PlatformKeys
        rows_result = await session.execute(
            select(PoolItem, Platform)
            .join(Platform, PoolItem.platform_id == Platform.id)
            .where(PoolItem.pool_id == pool.id, PoolItem.is_active == True)
            .options(selectinload(Platform.platform_keys))
            .order_by(PoolItem.priority)
        )
        rows = rows_result.all()

        health_items = []  # 所有 (pool_item, platform_key) 的 health 条目

        for pool_item, platform in rows:
            # 获取该 Platform 下所有 enabled 的 Keys
            enabled_keys = [k for k in platform.platform_keys if k.enabled and k.is_active]
            if not enabled_keys:
                # 没有 enabled keys，显示 Platform 整体状态（取第一个 disabled key）
                continue

            for key in enabled_keys:
                # 获取该 key 的 health state
                state = ph.get_platform_key_state(key.id)
                if state is None:
                    state = ph.PlatformKeyHealthState(
                        platform_key_id=key.id,
                        platform_id=platform.id,
                        key_label=key.label,
                    )
                    ph.register_platform_key_state(state)

                win = state.get_window(pool_item.model)
                rate_window = RateLimitWindow(
                    rpm=win.count(60),
                    rpd=win.count(86400),
                    tpm=win.tokens(60),
                    tpd=win.tokens(86400),
                )
                cooldown_until = None
                if state.cooldown_until and state.cooldown_until > time.time():
                    cooldown_until = datetime.fromtimestamp(
                        state.cooldown_until, tz=timezone.utc
                    ).isoformat()

                health_items.append(ProviderHealthItem(
                    provider_id=key.id,  # 复用 provider_id 字段（兼容前端）
                    provider_name=f"{platform.name} / {key.label or key.id}",
                    base_url=platform.base_url,
                    is_active=key.is_active,
                    platform_key_id=key.id,
                    key_label=key.label or str(key.id),
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
            providers=health_items,
        ))

    return HealthOverview(
        pools=out_pools,
        sticky_sessions_active=ph.StickySessionManager_instance.count(),
    )


@router.get("/rate-limit/{platform_key_id}")
async def platform_key_rate_limit(
    platform_key_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    返回单个 PlatformKey 的详细限流状态：
    - 各模型的滑动窗口用量
    - 当前冷却状态
    - 惩罚分
    """
    result = await session.execute(
        select(PlatformKey, Platform)
        .join(Platform, PlatformKey.platform_id == Platform.id)
        .where(PlatformKey.id == platform_key_id)
    )
    row = result.one_or_none()
    if not row:
        return {"error": "PlatformKey not found"}

    key, platform = row

    state = ph.get_platform_key_state(platform_key_id)
    if state is None:
        state = ph.PlatformKeyHealthState(
            platform_key_id=key.id,
            platform_id=platform.id,
            key_label=key.label,
        )
        ph.register_platform_key_state(state)

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
        "platform_key_id": platform_key_id,
        "key_label": key.label or str(key.id),
        "platform_name": platform.name,
        "platform_id": platform.id,
        "base_url": platform.base_url,
        "enabled": key.enabled,
        "is_active": key.is_active,
        "penalty_score": state.penalty_score,
        "strike_count": state.strike_count,
        "cooldown_until": cooldown_until,
        "cooldown_remaining_s": round(state.cooldown_remaining(), 1),
        "effective_priority_reduction": state.penalty_score,
        "model_windows": windows,
        "sticky_model": state.sticky_model,
    }