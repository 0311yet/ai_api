"""统计路由：Dashboard 概览 + 时序数据 + 按模型统计

Important: SQLite 下不能用 cast(..., Date) + ORM 自动转换，结果处理器遇到 `` 会崩。
改用 func.date() 返回纯字符串 'YYYY-MM-DD'，避免 SQLAlchemy 结果处理器介入。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware import verify_admin
from app.models import RequestLog, ClientKey, Pool, Provider, DailyStats, PoolItem
from app.schemas import (
    DashboardStats, TimeSeriesPoint, ModelStatRow, DailyStatsOut,
)

router = APIRouter(prefix="/admin/stats", tags=["stats"], dependencies=[Depends(verify_admin)])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(session: AsyncSession = Depends(get_session)):
    """Dashboard 顶部概览卡片：总请求/成功率/Token/延迟/活跃数"""
    # 总数
    total = (await session.execute(select(func.count(RequestLog.id)))).scalar() or 0
    success = (await session.execute(
        select(func.count(RequestLog.id)).where(RequestLog.status == "success")
    )).scalar() or 0
    failed = (await session.execute(
        select(func.count(RequestLog.id)).where(RequestLog.status == "failed")
    )).scalar() or 0

    # Token 聚合
    tokens = (await session.execute(
        select(
            func.coalesce(func.sum(RequestLog.total_tokens), 0),
            func.coalesce(func.sum(RequestLog.prompt_tokens), 0),
            func.coalesce(func.sum(RequestLog.completion_tokens), 0),
            func.coalesce(func.avg(RequestLog.latency_ms), 0),
            func.coalesce(func.avg(RequestLog.ttft_ms), 0),
        )
    )).one()
    total_tokens = tokens[0] or 0
    prompt_tokens = tokens[1] or 0
    completion_tokens = tokens[2] or 0

    # 活跃数（最近 1 小时内有活动的）
    active_keys = (await session.execute(
        select(func.count(ClientKey.id)).where(ClientKey.is_active == True)
    )).scalar() or 0
    active_pools = (await session.execute(
        select(func.count(Pool.id)).where(Pool.is_active == True)
    )).scalar() or 0
    active_providers = (await session.execute(
        select(func.count(Provider.id)).where(Provider.is_active == True)
    )).scalar() or 0

    success_rate = (success / total * 100) if total > 0 else 0

    # 成本计算：根据 request_logs JOIN pool_items JOIN providers 聚合
    # 按 provider.is_paid 选 free/paid 价，分别累加 free_cost / paid_cost
    # cost = prompt_tokens/1e6 * input_price + completion_tokens/1e6 * output_price
    # 在内存里聚合（SQLite 兼容性好、逻辑清晰）
    cost_rows = (await session.execute(
        select(
            RequestLog.pool_item_id,
            RequestLog.prompt_tokens,
            RequestLog.completion_tokens,
        )
        .select_from(RequestLog)
        .join(PoolItem, RequestLog.pool_item_id == PoolItem.id)
        .join(Provider, PoolItem.provider_id == Provider.id)
        .where(RequestLog.status == "success", RequestLog.pool_item_id.is_not(None))
    )).all()

    # 查所有涉及到的 PoolItem（含费率和 provider 的 is_paid）
    pitem_ids = {r[0] for r in cost_rows}
    item_map = {}
    if pitem_ids:
        items_data = (await session.execute(
            select(PoolItem, Provider)
            .join(Provider, PoolItem.provider_id == Provider.id)
            .where(PoolItem.id.in_(pitem_ids))
        )).all()
        for item, prov in items_data:
            item_map[item.id] = (item, prov)

    free_cost = 0.0
    paid_cost = 0.0
    for pool_item_id, pt, ct in cost_rows:
        entry = item_map.get(pool_item_id)
        if not entry:
            continue
        item, prov = entry
        if prov.is_paid:
            in_price = item.paid_input_price or 0
            out_price = item.paid_output_price or 0
            paid_cost += (pt or 0) / 1_000_000 * in_price + (ct or 0) / 1_000_000 * out_price
        else:
            in_price = item.free_input_price or 0
            out_price = item.free_output_price or 0
            free_cost += (pt or 0) / 1_000_000 * in_price + (ct or 0) / 1_000_000 * out_price

    return DashboardStats(
        total_requests=total,
        success_count=success,
        failed_count=failed,
        success_rate=round(success_rate, 2),
        total_tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        avg_latency_ms=round(tokens[3] or 0, 2),
        avg_ttft_ms=round(tokens[4] or 0, 2),
        active_keys=active_keys,
        active_pools=active_pools,
        active_providers=active_providers,
        free_cost=round(free_cost, 6),
        paid_cost=round(paid_cost, 6),
    )


@router.get("/timeseries", response_model=list[TimeSeriesPoint])
async def get_timeseries(
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
):
    """时序数据：最近 N 天，每天 1 个点（用于折线图/柱状图）

    用 func.date() 返回 'YYYY-MM-DD' 字符串，避免 SQLite 下 SQLAlchemy
    结果处理器尝试将 cast(..., Date) 结果转回 datetime 而崩溃。
    """
    start = datetime.now() - timedelta(days=days)

    rows = (await session.execute(
        select(
            func.date(RequestLog.created_at).label("d"),
            func.count(RequestLog.id).label("requests"),
            func.coalesce(func.sum(case(
                (RequestLog.status == "success", 1), else_=0,
            )), 0).label("success"),
            func.coalesce(func.sum(case(
                (RequestLog.status == "failed", 1), else_=0,
            )), 0).label("failed"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("tt"),
            func.coalesce(func.sum(RequestLog.prompt_tokens), 0).label("pt"),
            func.coalesce(func.sum(RequestLog.completion_tokens), 0).label("ct"),
            func.coalesce(func.avg(RequestLog.latency_ms), 0).label("lat"),
            func.coalesce(func.avg(RequestLog.ttft_ms), 0).label("ttft"),
        )
        .where(RequestLog.created_at >= start)
        .group_by("d")
        .order_by("d")
    )).all()

    return [
        TimeSeriesPoint(
            date=str(r.d) if r.d is not None else "",
            requests=r.requests,
            success=int(r.success or 0),
            failed=int(r.failed or 0),
            prompt_tokens=int(r.pt or 0),
            completion_tokens=int(r.ct or 0),
            total_tokens=int(r.tt),
            avg_latency_ms=round(r.lat or 0, 2),
            avg_ttft_ms=round(r.ttft or 0, 2),
        )
        for r in rows
    ]


@router.get("/by-model", response_model=list[ModelStatRow])
async def get_stats_by_model(session: AsyncSession = Depends(get_session)):
    """按模型聚合统计"""
    rows = (await session.execute(
        select(
            RequestLog.model,
            func.count(RequestLog.id).label("cnt"),
            func.coalesce(func.sum(case(
                (RequestLog.status == "success", 1), else_=0,
            )), 0).label("succ"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("tok"),
            func.coalesce(func.avg(RequestLog.latency_ms), 0).label("lat"),
        )
        .group_by(RequestLog.model)
        .order_by(desc("cnt"))
    )).all()

    return [
        ModelStatRow(
            model=r[0],
            request_count=r[1],
            success_count=int(r[2] or 0),
            total_tokens=int(r[3]),
            avg_latency_ms=round(r[4], 2),
        )
        for r in rows
    ]


@router.get("/daily", response_model=list[DailyStatsOut])
async def get_daily_stats(session: AsyncSession = Depends(get_session)):
    """查 DailyStats 表（后台聚合任务写入）"""
    rows = (await session.execute(
        select(DailyStats).order_by(desc(DailyStats.date))
    )).scalars().all()
    return rows
