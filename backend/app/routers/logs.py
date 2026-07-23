"""请求日志查询路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.database import get_session
from app.middleware import verify_admin
from app.models import RequestLog, PoolItem, Pool
from app.schemas import RequestLogOut, RequestLogDetail, ListResponse

router = APIRouter(prefix="/admin/logs", tags=["logs"], dependencies=[Depends(verify_admin)])


@router.get("", response_model=ListResponse)
async def list_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str = Query(default=""),
    model: str = Query(default=""),
    key_id: int = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    # LEFT JOIN pool_item + pool，预加载关系以便读取 upstream_model 和 pool_name
    q = (
        select(RequestLog)
        .outerjoin(PoolItem, RequestLog.pool_item_id == PoolItem.id)
        .outerjoin(Pool, PoolItem.pool_id == Pool.id)
        .options(
            selectinload(RequestLog.pool_item).selectinload(PoolItem.pool),
        )
    )
    count_q = select(func.count(RequestLog.id))

    if status:
        q = q.where(RequestLog.status == status)
        count_q = count_q.where(RequestLog.status == status)
    if model:
        q = q.where(RequestLog.model.contains(model))
        count_q = count_q.where(RequestLog.model.contains(model))
    if key_id:
        q = q.where(RequestLog.client_key_id == key_id)
        count_q = count_q.where(RequestLog.client_key_id == key_id)

    total = (await session.execute(count_q)).scalar()
    q = q.order_by(desc(RequestLog.id)).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(q)
    rows = result.scalars().all()

    items = [
        RequestLogOut.from_orm_with_pool(
            log,
            getattr(log, "pool_item", None),
            getattr(log.pool_item, "pool", None) if getattr(log, "pool_item", None) else None,
        )
        for log in rows
    ]
    return ListResponse(total=total, items=items)


@router.get("/{log_id}", response_model=RequestLogDetail)
async def get_log(log_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(RequestLog)
        .outerjoin(PoolItem, RequestLog.pool_item_id == PoolItem.id)
        .outerjoin(Pool, PoolItem.pool_id == Pool.id)
        .options(selectinload(RequestLog.pool_item).selectinload(PoolItem.pool))
        .where(RequestLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(404, "Log not found")
    return RequestLogOut.from_orm_with_pool(
        log,
        getattr(log, "pool_item", None),
        getattr(log.pool_item, "pool", None) if getattr(log, "pool_item", None) else None,
    )
