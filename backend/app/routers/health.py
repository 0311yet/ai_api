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
from app.schemas import KeyHealthItem, PoolItemHealthItem, RateLimitWindow, PoolHealthOut, HealthOverview
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
        # 查询 PoolItem + Platform + PlatformKeys（按 platform_id 而非 provider_id）
        rows_result = await session.execute(
            select(PoolItem, Platform)
            .join(Platform, PoolItem.platform_id == Platform.id)
            .where(PoolItem.pool_id == pool.id, PoolItem.is_active == True)
            .options(selectinload(Platform.platform_keys))
            .order_by(PoolItem.priority)
        )
        rows = rows_result.all()

        health_items = []  # 每行 = 一个 PoolItem × Platform 的组合

        for pool_item, platform in rows:
            enabled_keys = [k for k in platform.platform_keys if k.enabled and k.is_active]
            if not enabled_keys:
                continue

            # 为该 PoolItem 下的每个 Key 生成健康数据
            key_health_list = []
            for key in enabled_keys:
                state = ph.get_platform_key_state(key.id)
                if state is None:
                    state = ph.PlatformKeyHealthState(
                        platform_key_id=key.id,
                        platform_id=platform.id,
                        key_label=key.label,
                    )
                    ph.register_platform_key_state(state)

                win = state.get_window(pool_item.model)
                cooldown_until = None
                if state.cooldown_until and state.cooldown_until > time.time():
                    cooldown_until = datetime.fromtimestamp(
                        state.cooldown_until, tz=timezone.utc
                    ).isoformat()

                key_health_list.append(KeyHealthItem(
                    platform_key_id=key.id,
                    key_label=key.label or str(key.id),
                    is_active=key.is_active,
                    rate_window=RateLimitWindow(
                        rpm=win.count(60),
                        rpd=win.count(86400),
                        tpm=win.tokens(60),
                        tpd=win.tokens(86400),
                    ),
                    cooldown_until=cooldown_until,
                    strike_count=state.strike_count,
                    penalty_score=state.penalty_score,
                    effective_priority=pool_item.priority - state.penalty_score,
                ))

            health_items.append(PoolItemHealthItem(
                pool_item_id=pool_item.id,
                platform_id=platform.id,
                platform_name=platform.name,
                base_url=platform.base_url,
                model=pool_item.model,
                priority=pool_item.priority,
                is_active=pool_item.is_active,
                available_keys=key_health_list,
            ))

        out_pools.append(PoolHealthOut(
            pool_id=pool.id,
            pool_name=pool.name,
            strategy=pool.strategy,
            items=health_items,
        ))

    return HealthOverview(
        pools=out_pools,
        sticky_sessions_active=ph.StickySessionManager_instance.count(),
    )


@router.get("/debug/state")
async def debug_state():
    """临时 debug 端点：暴露内部 in-memory 状态"""
    from app.services import provider_health as ph
    return {
        "registered_keys": list(ph._PLATFORM_KEY_STATE.keys()),
        "event_buffer": {f"{pk_id}|{model}": v for (pk_id, model), v in ph._EVENT_BUFFER.items()},
        "bg_tasks_count": len(ph._BACKGROUND_TASKS),
        "key_details": {
            pk_id: {
                "key_label": state.key_label,
                "windows": {
                    model: {"rpm": sw.count(60), "rpd": sw.count(86400), "tpm": sw.tokens(60), "tpd": sw.tokens(86400)}
                    for model, sw in state.windows.items()
                },
                "cooldown_until": state.cooldown_until,
                "strike_count": state.strike_count,
            }
            for pk_id, state in ph._PLATFORM_KEY_STATE.items()
        },
    }

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