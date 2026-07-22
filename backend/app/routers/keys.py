"""ClientKey CRUD 路由"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.middleware import verify_admin
from app.models import ClientKey, Pool
from app.schemas import ClientKeyCreate, ClientKeyUpdate, ClientKeyOut

router = APIRouter(prefix="/admin/keys", tags=["keys"], dependencies=[Depends(verify_admin)])


def generate_key() -> str:
    """生成 sk- 前缀的客户端 key"""
    return "sk-" + secrets.token_urlsafe(32)


async def _key_to_out(key_obj: ClientKey) -> ClientKeyOut:
    """转换 + 附加 pool_name"""
    pool_name = None
    if key_obj.pool:
        pool_name = key_obj.pool.name
    return ClientKeyOut(
        id=key_obj.id,
        key=key_obj.key,
        name=key_obj.name,
        pool_id=key_obj.pool_id,
        pool_name=pool_name,
        allowed_models=key_obj.allowed_models or [],
        is_active=key_obj.is_active,
        request_count=key_obj.request_count,
        total_tokens=key_obj.total_tokens,
        created_at=key_obj.created_at,
        last_used_at=key_obj.last_used_at,
    )


@router.get("", response_model=list[ClientKeyOut])
async def list_keys(
    search: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    q = (
        select(ClientKey)
        .options(selectinload(ClientKey.pool))
        .order_by(ClientKey.id)
    )
    if search:
        q = q.where(
            (ClientKey.key.contains(search)) | (ClientKey.name.contains(search))
        )
    result = await session.execute(q)
    keys = result.scalars().all()
    return [await _key_to_out(k) for k in keys]


@router.post("", response_model=ClientKeyOut, status_code=201)
async def create_key(data: ClientKeyCreate, session: AsyncSession = Depends(get_session)):
    # 如果指明了 pool，确认 pool 存在
    if data.pool_id:
        pool = await session.get(Pool, data.pool_id)
        if not pool:
            raise HTTPException(400, f"Pool {data.pool_id} not found")

    key_obj = ClientKey(
        key=generate_key(),
        name=data.name,
        pool_id=data.pool_id,
        allowed_models=data.allowed_models,
        is_active=data.is_active,
    )
    session.add(key_obj)
    await session.commit()
    await session.refresh(key_obj)
    return await _key_to_out(key_obj)


@router.get("/{key_id}", response_model=ClientKeyOut)
async def get_key(key_id: int, session: AsyncSession = Depends(get_session)):
    key_obj = await session.get(ClientKey, key_id)
    if not key_obj:
        raise HTTPException(404, "Key not found")
    # 显式加载 pool 关系
    q = select(ClientKey).options(selectinload(ClientKey.pool)).where(ClientKey.id == key_id)
    key_obj = (await session.execute(q)).scalar_one()
    return await _key_to_out(key_obj)


@router.put("/{key_id}", response_model=ClientKeyOut)
async def update_key(
    key_id: int,
    data: ClientKeyUpdate,
    session: AsyncSession = Depends(get_session),
):
    key_obj = await session.get(ClientKey, key_id)
    if not key_obj:
        raise HTTPException(404, "Key not found")
    if data.pool_id is not None and data.pool_id > 0:
        pool = await session.get(Pool, data.pool_id)
        if not pool:
            raise HTTPException(400, f"Pool {data.pool_id} not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(key_obj, k, v)
    await session.commit()
    await session.refresh(key_obj)
    return await _key_to_out(key_obj)


@router.delete("/{key_id}")
async def delete_key(key_id: int, session: AsyncSession = Depends(get_session)):
    key_obj = await session.get(ClientKey, key_id)
    if not key_obj:
        raise HTTPException(404, "Key not found")
    await session.delete(key_obj)
    await session.commit()
    return {"message": "deleted"}
