"""数据模型定义"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Float, JSON, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Platform(Base):
    """
    上游 AI 模型厂商（如 NVIDIA NIM, Google, Groq）
    一个 Platform 下可以有多个 PlatformKey（多个 API Keys）
    """
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # "NVIDIA NIM"
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)  # "https://integrate.api.nvidia.com/v1"
    # 该平台支持的所有模型列表（JSON 字符串数组）
    models: Mapped[List] = mapped_column(JSON, default=list)
    # 是否为付费 API（True=付费，False=免费）。决定成本计算时用 paid 还是 free 价
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # 关联
    platform_keys: Mapped[List["PlatformKey"]] = relationship(back_populates="platform", cascade="all, delete-orphan")
    pool_items: Mapped[List["PoolItem"]] = relationship(back_populates="platform", cascade="all, delete-orphan")


class PlatformKey(Base):
    """
    平台 API 密钥（一个 Platform 下可以有多个 Key）
    同一个 Platform 下的多个 Keys 可以负载均衡和回退
    """
    __tablename__ = "platform_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped["Platform"] = relationship(back_populates="platform_keys")

    # API 密钥（存储时建议加密，但这里先明文存储）
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    # Key 标签（如 "main", "backup", "spare"）
    label: Mapped[str] = mapped_column(String(100), default="")
    # 该 Key 是否启用
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 该 Key 是否活跃（可删除但不删除记录）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # 唯一约束：同一 platform 下 api_key 不能重复
    __table_args__ = (
        UniqueConstraint('platform_id', 'api_key', name='uq_platform_key'),
    )


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
    """
    池内模型配置：一个 Pool 下有多个 PoolItem，每个指向某个 Platform 的某个 model
    注意：不再直接指向 Provider，而是指向 Platform
    """
    __tablename__ = "pool_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool_id: Mapped[int] = mapped_column(ForeignKey("pools.id", ondelete="CASCADE"), nullable=False)
    pool: Mapped["Pool"] = relationship(back_populates="pool_items")

    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped["Platform"] = relationship(back_populates="pool_items")

    # 上游真实 model 名（如 "z-ai/glm-5.2"）
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 费率：per 1M tokens 的价格。free_* 对应免费 API，paid_* 对应付费 API
    free_input_price: Mapped[float] = mapped_column(Float, default=0)
    free_output_price: Mapped[float] = mapped_column(Float, default=0)
    paid_input_price: Mapped[float] = mapped_column(Float, default=0)
    paid_output_price: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # 保留 provider_id 字段用于向后兼容（迁移期）
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)

    # 关联旧的 provider（用于迁移期兼容）
    provider: Mapped[Optional["Provider"]] = relationship(back_populates="pool_items")
    request_logs: Mapped[List["RequestLog"]] = relationship(back_populates="pool_item")


class ClientKey(Base):
    """客户端 API Key：下游用户调用网关用的 key"""
    __tablename__ = "client_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    pool_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pools.id", ondelete="SET NULL"))
    pool: Mapped[Optional["Pool"]] = relationship(back_populates="client_keys")
    allowed_models: Mapped[List] = mapped_column(JSON, default=list)  # 空数组=不限制
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class RequestLog(Base):
    """请求日志：每次调用 /v1/chat/completions 记一条"""
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client_keys.id", ondelete="SET NULL"))
    pool_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pool_items.id", ondelete="SET NULL"))
    pool_item: Mapped[Optional["PoolItem"]] = relationship(back_populates="request_logs")

    # 保留 provider_id 字段（现在改为 platform_key_id）
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)
    # 新增：指向 PlatformKey
    platform_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("platform_keys.id", ondelete="SET NULL"), nullable=True)

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


# ── Provider Health: 限流记录 + 冷却状态（保留向后兼容）───────────────────────

class Provider(Base):
    """
    旧的 Provider 模型（保留用于向后兼容迁移）
    迁移完成后可以删除
    """
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    models: Mapped[List] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # 关联（向后兼容）
    pool_items: Mapped[List["PoolItem"]] = relationship(back_populates="provider")


class RateLimitEvent(Base):
    """
    限流事件记录（用于滑动窗口统计）
    批量异步写入，不在请求关键路径上。
    迁移期保留 provider_id 字段，新增 platform_key_id 字段
    """
    __tablename__ = "rate_limit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 迁移期保留 provider_id，新增 platform_key_id
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)
    platform_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("platform_keys.id", ondelete="SET NULL"), nullable=True)
    model: Mapped[str] = mapped_column(String(100), default="")
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # request / token / 429_reject
    event_value: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class ProviderCooldown(Base):
    """
    Provider 冷却状态（冷却中跳过该 Provider）
    迁移期保留，新增 PlatformKeyCooldown
    """
    __tablename__ = "provider_cooldowns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    cooldown_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    strike_count: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(String(100), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class PlatformKeyCooldown(Base):
    """
    PlatformKey 冷却状态（冷却中跳过该 Key）
    这是新的冷却机制，针对每个 Key 单独冷却
    """
    __tablename__ = "platform_key_cooldowns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_key_id: Mapped[int] = mapped_column(
        ForeignKey("platform_keys.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    cooldown_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    strike_count: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(String(100), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())