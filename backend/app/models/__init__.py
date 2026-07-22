"""数据模型定义"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Float, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Provider(Base):
    """上游 AI 厂商"""
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    models: Mapped[List] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    pool_items: Mapped[List["PoolItem"]] = relationship(back_populates="provider", cascade="all, delete-orphan")


class Pool(Base):
    """模型池：客户端调用时传入的 model 名 = Pool.name"""
    __tablename__ = "pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(200))
    strategy: Mapped[str] = mapped_column(String(50), default="priority")  # priority/round_robin/weighted/random
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    pool_items: Mapped[List["PoolItem"]] = relationship(
        back_populates="pool",
        cascade="all, delete-orphan",
        order_by="PoolItem.priority",
    )
    client_keys: Mapped[List["ClientKey"]] = relationship(back_populates="pool")


class PoolItem(Base):
    """池内模型配置：一个 Pool 下有多个 PoolItem，每个指向某个 Provider 的某个 model"""
    __tablename__ = "pool_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool_id: Mapped[int] = mapped_column(ForeignKey("pools.id", ondelete="CASCADE"), nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # 上游真实 model 名
    priority: Mapped[int] = mapped_column(Integer, default=1)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    pool: Mapped["Pool"] = relationship(back_populates="pool_items")
    provider: Mapped["Provider"] = relationship(back_populates="pool_items")
    request_logs: Mapped[List["RequestLog"]] = relationship(back_populates="pool_item")


class ClientKey(Base):
    """客户端 API Key：下游用户调用网关用的 key"""
    __tablename__ = "client_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    pool_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pools.id", ondelete="SET NULL"))
    allowed_models: Mapped[List] = mapped_column(JSON, default=list)  # 空数组=不限制
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    pool: Mapped[Optional["Pool"]] = relationship(back_populates="client_keys")


class RequestLog(Base):
    """请求日志：每次调用 /v1/chat/completions 记一条"""
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client_keys.id", ondelete="SET NULL"))
    pool_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pool_items.id", ondelete="SET NULL"))
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("providers.id", ondelete="SET NULL"))
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # 客户端请求的 model（= pool.name）
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending/success/failed
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    ttft_ms: Mapped[float] = mapped_column(Float, default=0)  # Time To First Token
    error_message: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[str] = mapped_column(String(50), default="")
    user_agent: Mapped[str] = mapped_column(String(200), default="")
    request_body: Mapped[str] = mapped_column(Text, default="")
    response_body: Mapped[str] = mapped_column(Text, default="")
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    pool_item: Mapped[Optional["PoolItem"]] = relationship(back_populates="request_logs")


class DailyStats(Base):
    """每日聚合统计（后台每 5 分钟刷新）"""
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0)
    avg_ttft_ms: Mapped[float] = mapped_column(Float, default=0)
