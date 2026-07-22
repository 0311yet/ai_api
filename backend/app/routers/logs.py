"""请求日志查询路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware import verify_admin
from app.models import RequestLog
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
    q = select(RequestLog)
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
    items = result.scalars().all()

    return ListResponse(
        total=total,
        items=[RequestLogOut.model_validate(r) for r in items],
    )


@router.get("/{log_id}", response_model=RequestLogDetail)
async def get_log(log_id: int, session: AsyncSession = Depends(get_session)):
    log = await session.get(RequestLog, log_id)
    if not log:
        raise HTTPException(404, "Log not found")
    return log
