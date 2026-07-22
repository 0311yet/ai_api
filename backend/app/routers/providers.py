"""Provider CRUD 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware import verify_admin
from app.models import Provider
from app.schemas import ProviderCreate, ProviderUpdate, ProviderOut

router = APIRouter(prefix="/admin/providers", tags=["providers"], dependencies=[Depends(verify_admin)])


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    search: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    q = select(Provider).order_by(Provider.id)
    if search:
        q = q.where(Provider.name.contains(search))
    result = await session.execute(q)
    return result.scalars().all()


@router.post("", response_model=ProviderOut, status_code=201)
async def create_provider(data: ProviderCreate, session: AsyncSession = Depends(get_session)):
    provider = Provider(**data.model_dump())
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return provider


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(provider_id: int, session: AsyncSession = Depends(get_session)):
    provider = await session.get(Provider, provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    return provider


@router.put("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    session: AsyncSession = Depends(get_session),
):
    provider = await session.get(Provider, provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(provider, k, v)
    await session.commit()
    await session.refresh(provider)
    return provider


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, session: AsyncSession = Depends(get_session)):
    provider = await session.get(Provider, provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    await session.delete(provider)
    await session.commit()
    return {"message": "deleted"}
