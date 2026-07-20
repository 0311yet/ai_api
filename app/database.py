"""数据库配置"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from app.models import Base

DATABASE_URL = "sqlite+aiosqlite:///./ai_gateway.db"

# 同步引擎用于初始化
SYNC_DATABASE_URL = "sqlite:///./ai_gateway.db"


async def init_db():
    """初始化数据库"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def get_sync_engine():
    """获取同步引擎"""
    return create_engine(SYNC_DATABASE_URL, echo=False)


async def get_session():
    """获取数据库会话"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()