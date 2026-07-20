"""统计接口 - 用量、延迟、历史"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import RequestLog, Channel, DailyStats

router = APIRouter(prefix="/stats")


@router.get("/overview")
async def overview(session: AsyncSession = Depends(get_session)):
    """总览统计"""
    now = datetime.utcnow()
    
    # 总请求数
    total_req = await session.execute(select(func.count(RequestLog.id)))
    total_requests = total_req.scalar()
    
    # 成功/失败
    success_req = await session.execute(
        select(func.count(RequestLog.id)).where(RequestLog.status == "success")
    )
    success_count = success_req.scalar()
    failed_count = total_requests - success_count
    
    # 总token
    total_tokens_q = await session.execute(
        select(func.sum(RequestLog.total_tokens))
    )
    total_tokens = total_tokens_q.scalar() or 0
    
    # 平均延迟
    avg_latency_q = await session.execute(
        select(func.avg(RequestLog.latency_ms)).where(RequestLog.status == "success")
    )
    avg_latency = avg_latency_q.scalar() or 0
    
    # 平均TTFT
    avg_ttft_q = await session.execute(
        select(func.avg(RequestLog.ttft_ms)).where(RequestLog.status == "success", RequestLog.ttft_ms > 0)
    )
    avg_ttft = avg_ttft_q.scalar() or 0
    
    return {
        "total_requests": total_requests,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": round(success_count / total_requests * 100, 2) if total_requests > 0 else 0,
        "total_tokens": total_tokens,
        "avg_latency_ms": round(avg_latency, 2),
        "avg_ttft_ms": round(avg_ttft, 2),
    }


@router.get("/recent")
async def recent_stats(days: int = Query(7, ge=1, le=30), session: AsyncSession = Depends(get_session)):
    """最近N天的统计（默认7天）"""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    
    # 按天聚合
    stmt = text("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as request_count,
            SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_count,
            SUM(prompt_tokens) as prompt_tokens,
            SUM(completion_tokens) as completion_tokens,
            SUM(total_tokens) as total_tokens,
            AVG(CASE WHEN status='success' THEN latency_ms END) as avg_latency,
            AVG(CASE WHEN status='success' AND ttft_ms > 0 THEN ttft_ms END) as avg_ttft
        FROM request_logs
        WHERE created_at >= :since
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    result = await session.execute(stmt, {"since": since})
    rows = result.fetchall()
    
    return {
        "days": days,
        "data": [
            {
                "date": str(r[0]),
                "request_count": r[1] or 0,
                "success_count": r[2] or 0,
                "failed_count": r[3] or 0,
                "prompt_tokens": r[4] or 0,
                "completion_tokens": r[5] or 0,
                "total_tokens": r[6] or 0,
                "avg_latency_ms": round(r[7] or 0, 2),
                "avg_ttft_ms": round(r[8] or 0, 2),
            }
            for r in rows
        ]
    }


@router.get("/models")
async def model_stats(days: int = Query(7, ge=1, le=30), session: AsyncSession = Depends(get_session)):
    """按模型统计"""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    
    stmt = text("""
        SELECT 
            model,
            COUNT(*) as request_count,
            SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_count,
            SUM(prompt_tokens) as prompt_tokens,
            SUM(completion_tokens) as completion_tokens,
            SUM(total_tokens) as total_tokens,
            AVG(CASE WHEN status='success' THEN latency_ms END) as avg_latency,
            AVG(CASE WHEN status='success' AND ttft_ms > 0 THEN ttft_ms END) as avg_ttft
        FROM request_logs
        WHERE created_at >= :since
        GROUP BY model
        ORDER BY request_count DESC
    """)
    result = await session.execute(stmt, {"since": since})
    rows = result.fetchall()
    
    return {
        "days": days,
        "models": [
            {
                "model": r[0],
                "request_count": r[1] or 0,
                "success_count": r[2] or 0,
                "failed_count": r[3] or 0,
                "prompt_tokens": r[4] or 0,
                "completion_tokens": r[5] or 0,
                "total_tokens": r[6] or 0,
                "avg_latency_ms": round(r[7] or 0, 2),
                "avg_ttft_ms": round(r[8] or 0, 2),
            }
            for r in rows
        ]
    }


@router.get("/channels/{channel_id}")
async def channel_stats(channel_id: int, days: int = Query(7, ge=1, le=30), session: AsyncSession = Depends(get_session)):
    """按通道统计"""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    
    stmt = text("""
        SELECT 
            COUNT(*) as request_count,
            SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_count,
            SUM(prompt_tokens) as prompt_tokens,
            SUM(completion_tokens) as completion_tokens,
            SUM(total_tokens) as total_tokens,
            AVG(CASE WHEN status='success' THEN latency_ms END) as avg_latency,
            AVG(CASE WHEN status='success' AND ttft_ms > 0 THEN ttft_ms END) as avg_ttft
        FROM request_logs
        WHERE channel_id = :cid AND created_at >= :since
    """)
    result = await session.execute(stmt, {"cid": channel_id, "since": since})
    r = result.fetchone()
    
    return {
        "channel_id": channel_id,
        "days": days,
        "request_count": r[0] or 0,
        "success_count": r[1] or 0,
        "failed_count": r[2] or 0,
        "prompt_tokens": r[3] or 0,
        "completion_tokens": r[4] or 0,
        "total_tokens": r[5] or 0,
        "avg_latency_ms": round(r[6] or 0, 2),
        "avg_ttft_ms": round(r[7] or 0, 2),
    }


@router.get("/history")
async def request_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """请求历史"""
    stmt = select(RequestLog).order_by(RequestLog.created_at.desc())
    
    if model:
        stmt = stmt.where(RequestLog.model == model)
    if status:
        stmt = stmt.where(RequestLog.status == status)
    
    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar()
    
    # 分页
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    logs = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [
            {
                "id": log.id,
                "channel_id": log.channel_id,
                "model": log.model,
                "request_id": log.request_id,
                "prompt_tokens": log.prompt_tokens,
                "completion_tokens": log.completion_tokens,
                "total_tokens": log.total_tokens,
                "latency_ms": round(log.latency_ms, 2) if log.latency_ms else 0,
                "ttft_ms": round(log.ttft_ms, 2) if log.ttft_ms else 0,
                "status": log.status,
                "error_message": (log.error_message[:200] if log.error_message else None),
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }


@router.get("/history/{log_id}")
async def request_detail(log_id: int, session: AsyncSession = Depends(get_session)):
    """请求详情"""
    stmt = select(RequestLog).where(RequestLog.id == log_id)
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()
    if not log:
        return {"error": "Not found"}
    
    return {
        "id": log.id,
        "channel_id": log.channel_id,
        "key_id": log.key_id,
        "model": log.model,
        "request_id": log.request_id,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "total_tokens": log.total_tokens,
        "latency_ms": log.latency_ms,
        "ttft_ms": log.ttft_ms,
        "status": log.status,
        "error_message": log.error_message,
        "error_code": log.error_code,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "request_body": log.request_body,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }