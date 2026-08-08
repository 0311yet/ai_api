"""
PlatformKey Health Management API

GET /admin/health/overview          - 所有 Pool 的 PlatformKey 健康总览
GET /admin/health/rate-limit/<id>    - 单个 PlatformKey 限流详情

重构说明 (v1.3):
- 从 per-Provider 健康状态 → per-PlatformKey 健康状态
- PoolItem 的 health 状态现在归到其关联的 PlatformKey
- 同一个 PoolItem 的不同 Keys 显示为多个条目（支持多 Key 负载均衡展示）
"""
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Pool, PoolItem, Platform, PlatformKey, RequestLog
from app.schemas import (
    KeyHealthItem, PoolItemHealthItem, RateLimitWindow, PoolHealthOut,
    HealthOverview, PlatformsHealthOut, PlatformHealthItem, PlatformHealthKeyItem,
)
from app.services import provider_health as ph

router = APIRouter(prefix="/admin/health", tags=["health"])


@router.get("/providers")
async def provider_health_diagnostics(
    window_minutes: int = 15,
    session: AsyncSession = Depends(get_session),
):
    """Infer provider outages from recent routed request results.

    This is deliberately evidence-based: a provider is only marked as a
    suspected outage after multiple upstream 5xx/timeout/network failures,
    which avoids confusing a bad API key or a client request with a vendor
    incident.
    """
    window_minutes = max(1, min(window_minutes, 1440))
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    result = await session.execute(
        select(RequestLog, Platform)
        .join(Platform, RequestLog.platform_id == Platform.id)
        .where(RequestLog.created_at >= cutoff)
    )
    grouped = {}
    for log, platform in result.all():
        item = grouped.setdefault(platform.id, {
            "platform_id": platform.id,
            "platform_name": platform.name,
            "base_url": platform.base_url,
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "failure_types": {},
            "models": {},
            "keys": set(),
            "last_failure_at": None,
        })
        item["requests"] += 1
        if log.status == "success":
            item["successes"] += 1
        else:
            item["failures"] += 1
            failure_type = (log.error_message or "upstream_error").split(":", 1)[0]
            item["failure_types"][failure_type] = item["failure_types"].get(failure_type, 0) + 1
            if log.created_at and (item["last_failure_at"] is None or log.created_at > item["last_failure_at"]):
                item["last_failure_at"] = log.created_at
        if log.platform_key_id:
            item["keys"].add(log.platform_key_id)
        model_stats = item["models"].setdefault(log.model, {"requests": 0, "failures": 0})
        model_stats["requests"] += 1
        model_stats["failures"] += log.status != "success"

    output = []
    for item in grouped.values():
        upstream_failures = sum(
            count for kind, count in item["failure_types"].items()
            if kind in {"upstream_timeout", "upstream_network_error", "upstream_5xx"}
        )
        dominant = max(item["failure_types"], key=item["failure_types"].get, default=None)
        if upstream_failures >= 3 and item["successes"] == 0:
            status = "suspected_outage"
            reason = "multiple upstream failures with no successful request in the window"
        elif dominant == "upstream_auth_error" and item["failures"] >= 2:
            status = "credential_issue"
            reason = "upstream rejected the configured credentials"
        elif dominant == "upstream_rate_limited" and item["failures"] >= 2:
            status = "rate_limited"
            reason = "upstream returned repeated rate-limit responses"
        elif upstream_failures:
            status = "degraded"
            reason = "some upstream requests failed"
        else:
            status = "healthy"
            reason = "no classified upstream failure observed"

        output.append({
            "platform_id": item["platform_id"],
            "platform_name": item["platform_name"],
            "base_url": item["base_url"],
            "status": status,
            "reason": reason,
            "window_minutes": window_minutes,
            "requests": item["requests"],
            "successes": item["successes"],
            "failures": item["failures"],
            "success_rate": round(item["successes"] / item["requests"], 4) if item["requests"] else 0,
            "upstream_failure_count": upstream_failures,
            "failure_types": item["failure_types"],
            "models": item["models"],
            "observed_key_count": len(item["keys"]),
            "last_failure_at": item["last_failure_at"].isoformat() if item["last_failure_at"] else None,
        })
    return {"window_minutes": window_minutes, "providers": sorted(output, key=lambda x: x["platform_name"])}


@router.get("/overview", response_model=HealthOverview)
async def health_overview(session: AsyncSession = Depends(get_session)):
    """
    Return all Pool's PlatformKey health status:
    - Each PoolItem x PlatformKey combo = one entry (all keys' health status)
    - Sliding window usage (RPM/RPD/TPM/TPD)
    - Cooldown status
    - Penalty score
    - Effective priority
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


@router.get("/platforms", response_model=PlatformsHealthOut)
async def health_platforms(session: AsyncSession = Depends(get_session)):
    """
    Per-platform health overview (no model layer):
    """
    result = await session.execute(
        select(Platform).options(selectinload(Platform.platform_keys)).order_by(Platform.name)
    )
    platforms = result.scalars().all()
    out_platforms = []

    for platform in platforms:
        enabled_keys = [k for k in platform.platform_keys if k.enabled and k.is_active]
        if not enabled_keys:
            continue

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

            # Aggregate all models' windows for this Key
            total_rpm = 0
            total_rpd = 0
            total_tpm = 0
            total_tpd = 0
            for model, win in state.windows.items():
                total_rpm += win.count(60)
                total_rpd += win.count(86400)
                total_tpm += win.tokens(60)
                total_tpd += win.tokens(86400)

            cooldown_until = None
            if state.cooldown_until and state.cooldown_until > time.time():
                cooldown_until = datetime.fromtimestamp(
                    state.cooldown_until, tz=timezone.utc
                ).isoformat()

            key_health_list.append(PlatformHealthKeyItem(
                platform_key_id=key.id,
                key_label=key.label or str(key.id),
                is_active=key.is_active,
                rate_window=RateLimitWindow(
                    rpm=total_rpm,
                    rpd=total_rpd,
                    tpm=total_tpm,
                    tpd=total_tpd,
                ),
                cooldown_until=cooldown_until,
                strike_count=state.strike_count,
                penalty_score=state.penalty_score,
            ))

        out_platforms.append(PlatformHealthItem(
            platform_id=platform.id,
            platform_name=platform.name,
            base_url=platform.base_url,
            keys=key_health_list,
        ))

    return PlatformsHealthOut(
        platforms=out_platforms,
        sticky_sessions_active=ph.StickySessionManager_instance.count(),
    )


@router.get("/rate-limit/{platform_key_id}")
async def platform_key_rate_limit(
    platform_key_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Return single PlatformKey rate limit detail:
    - Sliding window usage per model
    - Current cooldown status
    - Penalty score
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
