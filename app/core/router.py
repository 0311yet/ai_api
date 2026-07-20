"""路由匹配 - 根据模型名查找通道"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Channel


async def find_channels_for_model(session: AsyncSession, model_name: str) -> list[Channel]:
    """找到所有支持该模型的可用通道（按优先级排序）"""
    stmt = select(Channel).where(Channel.is_active == True)
    result = await session.execute(stmt)
    channels = result.scalars().all()
    
    matched = []
    for channel in channels:
        if channel.models is None:
            continue
        # 模型在通道支持列表中
        if model_name in channel.models:
            matched.append(channel)
    
    # 默认通道优先
    matched.sort(key=lambda c: not c.is_default)
    return matched


async def get_default_channels(session: AsyncSession) -> list[Channel]:
    """获取所有默认通道（兜底路由）"""
    stmt = select(Channel).where(
        Channel.is_active == True,
        Channel.is_default == True
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())