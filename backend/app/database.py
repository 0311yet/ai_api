"""数据库连接 - SQLAlchemy 异步引擎"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass




engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    # SQLite 需要这个才能支持 ALTER TABLE 等操作
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    """FastAPI 依赖：获取数据库会话"""
    async with async_session() as session:
        yield session


async def _ensure_columns(conn):
    """为新增字段自动 ALTER TABLE ADD COLUMN（升级时调用，重复执行也安全）"""
    from sqlalchemy import text, inspect

    def _do(sync_conn):
        insp = inspect(sync_conn)

        def has_column(table: str, column: str) -> bool:
            return column in [c["name"] for c in insp.get_columns(table)]

        #/providers.is_paid
        if not has_column("providers", "is_paid"):
            sync_conn.execute(text("ALTER TABLE providers ADD COLUMN is_paid BOOLEAN DEFAULT 0 NOT NULL"))

        # pool_items 的 4 个费率字段
        for col in ["free_input_price", "free_output_price", "paid_input_price", "paid_output_price"]:
            if not has_column("pool_items", col):
                sync_conn.execute(text(f"ALTER TABLE pool_items ADD COLUMN {col} FLOAT DEFAULT 0 NOT NULL"))

    await conn.run_sync(_do)


async def init_db():
    """初始化数据库（建表 + 开启 WAL 模式 + 自动增列）"""
    # 导入所有模型让 Base.metadata 注册所有表
    from app import models  # noqa: F401

    # SQLite WAL 模式：提高读写并发性能
    if settings.DATABASE_URL.startswith("sqlite"):
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))

    # 建表（开发阶段用，生产用 Alembic 迁移）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 自动给增量字段补列（兼容旧库）
        await _ensure_columns(conn)
