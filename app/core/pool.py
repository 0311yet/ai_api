"""模型池 - 密钥管理和负载均衡"""
import asyncio
import random
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Key, Channel


class KeyPool:
    """密钥池管理"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._locks: dict[int, asyncio.Lock] = {}  # 每个通道的锁
        self._indexes: dict[int, int] = {}  # 轮询索引
    
    def _get_lock(self, channel_id: int) -> asyncio.Lock:
        """获取通道锁"""
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]
    
    async def get_available_key(self, channel_id: int) -> Optional[Key]:
        """从池中获取可用密钥（带锁的轮询）"""
        lock = self._get_lock(channel_id)
        async with lock:
            return await self._select_key(channel_id)
    
    async def _select_key(self, channel_id: int) -> Optional[Key]:
        """选择密钥（轮询+权重+故障转移）"""
        # 查询可用密钥
        stmt = select(Key).where(
            Key.channel_id == channel_id,
            Key.is_active == True,
            Key.is_blocked == False
        )
        result = await self.session.execute(stmt)
        keys = list(result.scalars().all())
        
        if not keys:
            return None
        
        # 权重随机选择
        weights = [k.weight for k in keys]
        total_weight = sum(weights)
        r = random.uniform(0, total_weight)
        
        cumulative = 0
        for key in keys:
            cumulative += key.weight
            if r <= cumulative:
                # 更新使用记录
                key.request_count += 1
                key.last_used_at = datetime.utcnow()
                await self.session.commit()
                return key
        
        # 默认返回最后一个
        return keys[-1]
    
    async def report_error(self, key_id: int, error: str):
        """报告密钥错误"""
        stmt = update(Key).where(Key.id == key_id).values(
            error_count=Key.error_count + 1,
            last_error=error[:500]
        )
        await self.session.execute(stmt)
        await self.session.commit()
    
    async def block_key(self, key_id: int):
        """封禁密钥"""
        stmt = update(Key).where(Key.id == key_id).values(is_blocked=True)
        await self.session.execute(stmt)
        await self.session.commit()
    
    async def get_key_status(self, channel_id: int) -> dict:
        """获取密钥状态"""
        stmt = select(Key).where(Key.channel_id == channel_id)
        result = await self.session.execute(stmt)
        keys = result.scalars().all()
        
        return {
            "total": len(keys),
            "active": len([k for k in keys if k.is_active and not k.is_blocked]),
            "blocked": len([k for k in keys if k.is_blocked]),
            "keys": [
                {
                    "id": k.id,
                    "name": k.name,
                    "is_active": k.is_active,
                    "is_blocked": k.is_blocked,
                    "request_count": k.request_count,
                    "error_count": k.error_count,
                    "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                    "last_error": k.last_error
                }
                for k in keys
            ]
        }