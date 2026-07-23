"""Pydantic schemas - 请求与响应模型"""
from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel, Field


# ---------------- Provider ----------------
class ProviderBase(BaseModel):
    name: str
    base_url: str
    api_key: str
    models: List[str] = Field(default_factory=list)
    is_active: bool = True


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_paid: Optional[bool] = None


class ProviderOut(ProviderBase):
    id: int
    is_paid: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------- Platform ----------------
class PlatformBase(BaseModel):
    name: str
    base_url: str
    models: List[str] = Field(default_factory=list)
    is_paid: bool = False
    is_active: bool = True


class PlatformCreate(PlatformBase):
    pass


class PlatformUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    models: Optional[List[str]] = None
    is_paid: Optional[bool] = None
    is_active: Optional[bool] = None


class PlatformOut(PlatformBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------- PlatformKey ----------------
class PlatformKeyBase(BaseModel):
    api_key: str
    label: str = ""
    enabled: bool = True


class PlatformKeyCreate(PlatformKeyBase):
    platform_id: int


class PlatformKeyUpdate(BaseModel):
    api_key: Optional[str] = None
    label: Optional[str] = None
    enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class PlatformKeyOut(PlatformKeyBase):
    id: int
    platform_id: int
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlatformDetailOut(PlatformOut):
    platform_keys: List[PlatformKeyOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ---------------- Pool ----------------
class PoolItemBase(BaseModel):
    # 支持 platform_id（新） 和 provider_id（兼容旧）
    platform_id: Optional[int] = None
    provider_id: Optional[int] = None
    model: str
    priority: int = 1
    weight: int = 1
    is_active: bool = True
    # 可选：指定具体的 PlatformKey（如果不指定，路由时会使用该 Platform 下所有 enabled 的 Keys）
    platform_key_id: Optional[int] = None
    key_label: str = ""


class PoolItemCreate(PoolItemBase):
    pass


class PoolItemOut(PoolItemBase):
    id: int
    pool_id: int
    platform_name: Optional[str] = None  # 来自 join
    provider_name: Optional[str] = None  # 兼容旧
    # 费率：per 1M tokens
    free_input_price: float = 0
    free_output_price: float = 0
    paid_input_price: float = 0
    paid_output_price: float = 0
    created_at: datetime

    class Config:
        from_attributes = True


class PoolItemPriceUpdate(BaseModel):
    """单独更新某个 PoolItem 的费率"""
    free_input_price: Optional[float] = None
    free_output_price: Optional[float] = None
    paid_input_price: Optional[float] = None
    paid_output_price: Optional[float] = None


class PoolBase(BaseModel):
    name: str
    display_name: Optional[str] = None
    strategy: str = "priority"  # priority/round_robin/weighted/random
    is_active: bool = True


class PoolCreate(PoolBase):
    items: List[PoolItemCreate] = Field(default_factory=list)


class PoolUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    strategy: Optional[str] = None
    is_active: Optional[bool] = None


class PoolOut(PoolBase):
    id: int
    created_at: datetime
    items: List[PoolItemOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ---------------- ClientKey ----------------
class ClientKeyCreate(BaseModel):
    name: Optional[str] = None
    pool_id: Optional[int] = None
    allowed_models: List[str] = Field(default_factory=list)
    is_active: bool = True


class ClientKeyUpdate(BaseModel):
    name: Optional[str] = None
    pool_id: Optional[int] = None
    allowed_models: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ClientKeyOut(BaseModel):
    id: int
    key: str
    name: Optional[str] = None
    pool_id: Optional[int] = None
    pool_name: Optional[str] = None
    allowed_models: List[str] = Field(default_factory=list)
    is_active: bool = True
    request_count: int = 0
    total_tokens: int = 0
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------- RequestLog ----------------
class RequestLogOut(BaseModel):
    id: int
    client_key_id: Optional[int]
    pool_item_id: Optional[int]
    provider_id: Optional[int]  # 兼容旧数据
    platform_id: Optional[int] = None
    platform_key_id: Optional[int] = None
    # 客户端请求的 model（= pool.name，如 "auto"）
    model: str
    # 上游实际调用的模型名称（来自 PoolItem.model）
    upstream_model: Optional[str] = None
    # 所属模型池名称（来自 Pool.name）
    pool_name: Optional[str] = None
    request_id: str
    status: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    ttft_ms: float
    error_message: str
    ip_address: str
    is_stream: bool
    created_at: datetime

    @classmethod
    def from_orm_with_pool(cls, log, pool_item, pool) -> "RequestLogOut":
        """从 ORM 对象构造，附加 pool_item 和 pool 的字段"""
        upstream = pool_item.model if pool_item else None
        pool_nm = pool.name if pool else None
        return cls(
            id=log.id,
            client_key_id=log.client_key_id,
            pool_item_id=log.pool_item_id,
            provider_id=log.provider_id,
            platform_id=getattr(log, 'platform_id', None),
            platform_key_id=getattr(log, 'platform_key_id', None),
            model=log.model,
            upstream_model=upstream,
            pool_name=pool_nm,
            request_id=log.request_id,
            status=log.status,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            total_tokens=log.total_tokens,
            latency_ms=log.latency_ms,
            ttft_ms=log.ttft_ms,
            error_message=log.error_message,
            ip_address=log.ip_address,
            is_stream=log.is_stream,
            created_at=log.created_at,
        )

    class Config:
        from_attributes = True


class RequestLogDetail(RequestLogOut):
    user_agent: str
    request_body: str
    response_body: str


# ---------------- Stats ----------------
class DashboardStats(BaseModel):
    total_requests: int
    success_count: int
    failed_count: int
    success_rate: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: float
    avg_ttft_ms: float
    active_keys: int
    active_pools: int
    active_providers: int
    # 累计成本（根据 request_logs + pool_items 价格 + provider.is_paid 计算）
    free_cost: float = 0
    paid_cost: float = 0


class TimeSeriesPoint(BaseModel):
    date: str
    requests: int = 0
    success: int = 0
    failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0
    avg_ttft_ms: float = 0


class ModelStatRow(BaseModel):
    model: str
    request_count: int
    success_count: int
    total_tokens: int
    avg_latency_ms: float


class DailyStatsOut(BaseModel):
    date: str
    request_count: int
    success_count: int
    failed_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    avg_latency_ms: float
    avg_ttft_ms: float

    class Config:
        from_attributes = True


# ---------------- 通用响应 ----------------
class ListResponse(BaseModel):
    """列表响应包装"""
    total: int
    items: List[Any]


class MessageResponse(BaseModel):
    message: str


# ── PlatformKey Health ──────────────────────────────────────────
class RateLimitWindow(BaseModel):
    """单个时间窗口的用量"""
    rpm: int = 0
    rpd: int = 0
    tpm: int = 0
    tpd: int = 0


class ProviderHealthItem(BaseModel):
    """单个 Provider 的健康状态（保留旧名，内部迁移到 PlatformKey）"""
    provider_id: int
    provider_name: str
    base_url: str
    is_active: bool
    # 新增：platform_key_id 和 key_label
    platform_key_id: Optional[int] = None
    key_label: str = ""
    # 当前绑定的模型（来自 pool_item.model）
    model: Optional[str] = None
    # 滑动窗口（从 DB 实时查）
    rate_window: RateLimitWindow
    # 冷却状态（无冷却则 cooldown_until 为空）
    cooldown_until: Optional[str] = None  # ISO 字符串，无冷却时 null
    strike_count: int = 0
    # 惩罚分
    penalty_score: int = 0
    # 有效优先级（基础 - 惩罚分）
    effective_priority: int = 0


class PoolHealthOut(BaseModel):
    pool_id: int
    pool_name: str
    strategy: str
    providers: List[ProviderHealthItem]


class HealthOverview(BaseModel):
    """Provider 健康总览"""
    pools: List[PoolHealthOut]
    sticky_sessions_active: int