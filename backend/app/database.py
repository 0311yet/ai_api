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
    """Fix column nullability for upgraded DBs (call on init, idempotent)."""
    from sqlalchemy import text, inspect

    def _do(sync_conn):
        insp = inspect(sync_conn)

        def has_column(table: str, column: str) -> bool:
            return column in [c["name"] for c in insp.get_columns(table)]

        def col_nullable(table: str, column: str) -> bool:
            """Check column nullable. Returns True if nullable."""
            if not has_column(table, column):
                return True
            r = sync_conn.execute(text(f"PRAGMA table_info({table})"))
            for row in r:
                if row[1] == column:
                    return row[3] == 0  # 4th field = notnull; 0 = nullable
            return True

        #/providers.is_paid
        if not has_column("providers", "is_paid"):
            sync_conn.execute(text("ALTER TABLE providers ADD COLUMN is_paid BOOLEAN DEFAULT 0 NOT NULL"))

        # pool_items: add 4 rate columns if missing
        for col in ["free_input_price", "free_output_price", "paid_input_price", "paid_output_price"]:
            if not has_column("pool_items", col):
                sync_conn.execute(text(f"ALTER TABLE pool_items ADD COLUMN {col} FLOAT DEFAULT 0 NOT NULL"))

        # pool_items.provider_id: drop NOT NULL (SQLite needs table rebuild)
        # New architecture uses platform_id; provider_id is optional legacy.
        if has_column("pool_items", "provider_id") and not col_nullable("pool_items", "provider_id"):
            _sqlite_make_nullable(sync_conn, "pool_items", "provider_id")

    await conn.run_sync(_do)


def _sqlite_make_nullable(sync_conn, table: str, column: str):
    """Rebuild a SQLite table to make a column nullable.

    SQLite cannot ALTER COLUMN ... DROP NOT NULL directly, so:
    1. Create temp table with desired schema (column nullable)
    2. Copy data
    3. Drop old, rename temp
    """
    from sqlalchemy import text
    # Get original CREATE SQL
    r = sync_conn.execute(text(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'"))
    create_sql = r.scalar()
    if not create_sql:
        return
    # Make target column nullable in the CREATE SQL
    # SQLite stores NOT NULL as inline constraint. Replace `column` INTEGER/TEXT NOT NULL ... with nullable version
    import re
    # tolerant regex matching: `column` <TYPE> NOT NULL
    new_sql = re.sub(
        r'("?'+column+r'"?)\s+(INTEGER|TEXT|VARCHAR\(\d+\))\s+NOT\s+NULL',
        r'\1 \2',
        create_sql,
        flags=re.IGNORECASE,
    )
    if new_sql == create_sql:
        return  # nothing changed / already nullable / regex miss
    sqls = [
        f"PRAGMA foreign_keys=OFF",
        f"BEGIN TRANSACTION",
        f"ALTER TABLE {table} RENAME TO {table}__old",
        new_sql,
        f"INSERT INTO {table} SELECT * FROM {table}__old",
        f"DROP TABLE {table}__old",
        f"COMMIT",
        f"PRAGMA foreign_keys=ON",
    ]
    for sql in sqls:
        sync_conn.execute(text(sql))


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
