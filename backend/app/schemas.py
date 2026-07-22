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


class ProviderOut(ProviderBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------- Pool ----------------
class PoolItemBase(BaseModel):
    provider_id: int
    model: str
    priority: int = 1
    weight: int = 1
    is_active: bool = True


class PoolItemCreate(PoolItemBase):
    pass


class PoolItemOut(PoolItemBase):
    id: int
    pool_id: int
    provider_name: Optional[str] = None  # 来自 join
    created_at: datetime

    class Config:
        from_attributes = True


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
    provider_id: Optional[int]
    model: str
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


# ── Provider Health ───────────────────────────────────────────────
class RateLimitWindow(BaseModel):
    """单个时间窗口的用量"""
    rpm: int = 0
    rpd: int = 0
    tpm: int = 0
    tpd: int = 0


class ProviderHealthItem(BaseModel):
    """单个 Provider 的健康状态"""
    provider_id: int
    provider_name: str
    base_url: str
    is_active: bool
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
