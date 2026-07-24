"""
Provider Health 模块：速率限制跟踪、冷却管理、惩罚评分、粘性会话

重构说明 (v1.3):
- 从 ProviderState → PlatformKeyHealthState (per-key tracking)
- ProviderHealthManager → PlatformKeyHealthManager
- 冷却和惩罚现在针对每个 PlatformKey 单独处理，而不是整个 Platform

好处：
- 同一 Platform 下多个 Keys 可以独立负载均衡和回退
- 当一个 Key 被 429 时，只惩罚该 Key，不影响其他 Keys
- 解决 NVIDIA NIM 全局限速导致的全部 Providers 变红问题
"""
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, Optional, Tuple
import time
from datetime import datetime, timezone, timedelta
import asyncio
from sqlalchemy import select, delete, func as sql_func, text

from app.database import async_session


# ── 配置常量 ────────────────────────────────────────────────────────

_MAX_STRIKE = 4
_COOLDOWN_FOR_STRIKE = {
    1: timedelta(minutes=2),
    2: timedelta(minutes=10),
    3: timedelta(hours=1),
    4: timedelta(hours=24),
}

_FLUSH_INTERVAL = 5
_CLEANUP_INTERVAL = 3600
_PENALTY_DECAY_INTERVAL = 120


def _cooldown_for_strike(strike: int) -> timedelta:
    idx = min(strike - 1, _MAX_STRIKE - 1)
    return _COOLDOWN_FOR_STRIKE[strike]


# ── 滑动窗口（每分钟一条汇总，节省内存）─────────────────────────

@dataclass
class MinuteBucket:
    ts: float           # 该分钟开始时间（unix）
    request_count: int = 0
    token_count: int = 0

    @property
    def expired(self, window_seconds: float) -> bool:
        return (time.time() - self.ts) > window_seconds


class SlidingWindow:
    """
    滑动窗口：用于 RPM/RPD/TPM/TPD 统计。

    重要：_get_buckets_in_window() 是纯只读（不 pop）。
    过期清理只在 add() 路径调用 _evict_expired()。
    这样同一个 deque 可以同时服务 60s 和 24h 窗口查询，互不破坏。
    """

    MAX_BUCKETS = 8640   # 留点余量

    def __init__(self):
        self._buckets: deque[MinuteBucket] = deque()   # 按时间升序

    def _current_minute(self) -> float:
        """返回当前整分钟的时间戳（秒）"""
        return int(time.time() // 60) * 60.0

    def add(self, token_count: int = 1):
        """写入一条请求事件。

        bucket 时间戳用请求实际发生时刻 (time.time())，而非整分钟起点，
        这样 count(60) 才是真正的 60 秒滑动窗口——请求后恰好 60 秒过期。
        同一分钟内的多次请求合并到该分钟的首个 bucket（按分钟对齐判断）。
        """
        # 写入时借机清理超过 24h 的 bucket，避免 deque 无限增长
        self._evict_expired(86400)
        now = time.time()
        now_min = int(now // 60) * 60.0
        if self._buckets and abs(self._buckets[-1].ts - now_min) < 1e-6:
            # 同一分钟，合并到该 bucket（首条请求的时间戳保留）
            self._buckets[-1].request_count += 1
            self._buckets[-1].token_count += token_count
        else:
            # 新分钟，新建 bucket，时间戳用请求实际时刻
            self._buckets.append(MinuteBucket(ts=now, request_count=1, token_count=token_count))

    def _get_buckets_in_window(self, window_seconds: float) -> list:
        """返回窗口内所有 bucket（只读，不修改 deque）。"""
        cutoff = time.time() - window_seconds
        # 过滤而非 popleft，保持非破坏性
        return [b for b in self._buckets if b.ts >= cutoff]

    def _evict_expired(self, max_age_seconds: float = 86400) -> None:
        """真正 popleft 删除超过 max_age 的 bucket，由 add() 在写入路径调用。"""
        cutoff = time.time() - max_age_seconds
        while self._buckets and self._buckets[0].ts < cutoff:
            self._buckets.popleft()

    def count(self, window_seconds: float) -> int:
        return sum(b.request_count for b in self._get_buckets_in_window(window_seconds))

    def tokens(self, window_seconds: float) -> int:
        return sum(b.token_count for b in self._get_buckets_in_window(window_seconds))

    def to_snapshot(self) -> dict:
        """序列化，用于 DB flush"""
        return {
            "buckets": [(b.ts, b.request_count, b.token_count) for b in self._buckets]
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "SlidingWindow":
        """从 DB 恢复"""
        sw = cls()
        for ts, req_count, tok_count in snapshot.get("buckets", []):
            sw._buckets.append(MinuteBucket(ts=ts, request_count=req_count, token_count=tok_count))
        return sw


# ── PlatformKeyHealthState（单个 Key 的健康状态）──────────────────────

@dataclass
class PlatformKeyHealthState:
    """单个 PlatformKey 的健康状态（替代旧 ProviderState）"""
    platform_key_id: int
    platform_id: int
    key_label: str
    cooldown_until: Optional[float] = None  # unix timestamp，无冷却时 None
    strike_count: int = 0
    penalty_score: int = 0
    last_decay: float = field(default_factory=time.time)
    # Sticky Session 绑定
    sticky_model: Optional[str] = None

    # model -> SlidingWindow（每个上游模型一个窗口）
    windows: Dict[str, SlidingWindow] = field(default_factory=dict)

    def get_window(self, model: str = "") -> SlidingWindow:
        if model not in self.windows:
            self.windows[model] = SlidingWindow()
        return self.windows[model]

    def is_in_cooldown(self) -> bool:
        if self.cooldown_until is None:
            return False
        return time.time() < self.cooldown_until

    def cooldown_remaining(self) -> float:
        if self.cooldown_until is None:
            return 0
        rem = self.cooldown_until - time.time()
        return max(0, rem)

    def can_serve(self, model: str = "") -> tuple[bool, str]:
        """检查该 key 是否可用于服务请求。返回 (can_serve, reason)。"""
        if not self.is_in_cooldown():
            return True, ""
        remain = int(self.cooldown_remaining())
        return False, f"cooldown_{remain}s"

    def record_429(self, reason: str = "rate_limited"):
        """收到 429：加惩罚分 + 升级冷却"""
        self.penalty_score = min(10, self.penalty_score + 3)
        self.strike_count += 1
        dur = _cooldown_for_strike(self.strike_count)
        self.cooldown_until = time.time() + dur.total_seconds()
        return dur

    def record_success(self):
        """成功请求：惩罚分 -1"""
        if self.penalty_score > 0:
            self.penalty_score -= 1

    def decay_penalty(self) -> bool:
        """惩罚分衰减，返回是否还有剩余"""
        if self.penalty_score > 0:
            self.penalty_score = max(0, self.penalty_score - 1)
            self.last_decay = time.time()
        return self.penalty_score > 0

    def effective_priority(self, base_priority: int) -> int:
        """有效优先级 = 基础优先级 - 惩罚分"""
        return base_priority - self.penalty_score


# ── 全局单例 ─────────────────────────────────────────────────────

_PLATFORM_KEY_STATE: Dict[int, PlatformKeyHealthState] = {}  # platform_key_id -> state
_BACKGROUND_TASKS: list = []
_EVENT_BUFFER: Dict[tuple[int, str], dict] = {}  # (platform_key_id, model) -> {request, token, ts}
_EVENT_BUFFER_LOCK = None


def register_platform_key_state(state: PlatformKeyHealthState) -> None:
    """注册一个 PlatformKey 状态"""
    _PLATFORM_KEY_STATE[state.platform_key_id] = state


def get_platform_key_state(platform_key_id: int) -> Optional[PlatformKeyHealthState]:
    """获取 PlatformKey 状态（不存在返回 None）"""
    return _PLATFORM_KEY_STATE.get(platform_key_id)


def get_all_platform_key_states() -> Dict[int, PlatformKeyHealthState]:
    """获取所有 PlatformKey 状态"""
    return _PLATFORM_KEY_STATE.copy()


def clear_platform_key_states() -> None:
    """清空所有状态（测试用）"""
    _PLATFORM_KEY_STATE.clear()


# ── 异步 API（兼容旧接口名称，但内部实现变为 PlatformKey）──────────────

# 为了向后兼容，保留旧接口名称（实际使用新实现）
ProviderState = PlatformKeyHealthState
_PROVIDER_STATE = _PLATFORM_KEY_STATE  # 别名

def register_provider(state: PlatformKeyHealthState) -> None:
    """旧接口（兼容）"""
    register_platform_key_state(state)

def get_provider_state(provider_id: int) -> Optional[PlatformKeyHealthState]:
    """旧接口（兼容）- 按旧 provider_id 查找（已废弃）"""
    # 迁移期兼容：provider_id → platform_key_id 查找
    # TODO: 迁移完成后删除
    return None


# ── Sticky Session Manager ───────────────────────────────────────

@dataclass
class StickyEntry:
    platform_key_id: int
    model: str
    created_at: float
    expires_at: float    # now + 30min

    def valid(self) -> bool:
        return time.time() < self.expires_at


class StickySessionManager:
    """粘性会话管理：会话首次命中某个 key 后，后续相同会话继续使用该 key"""

    def __init__(self):
        self.sessions: Dict[str, StickyEntry] = {}

    @staticmethod
    def make_key(ip: str, first_user_message: str) -> str:
        """生成会话 key（简单版）"""
        return f"{ip}:{hash(first_user_message) % 1000000}"

    def bind(self, session_key: str, platform_key_id: int, model: str, ttl_seconds: int = 1800) -> None:
        now = time.time()
        entry = StickyEntry(
            platform_key_id=platform_key_id,
            model=model,
            created_at=now,
            expires_at=now + ttl_seconds,
        )
        self.sessions[session_key] = entry

        # 同时更新 state.sticky_model
        state = get_platform_key_state(platform_key_id)
        if state:
            state.sticky_model = model

    def get(self, session_key: str) -> Optional[StickyEntry]:
        entry = self.sessions.get(session_key)
        if entry and entry.valid():
            return entry
        # 清理过期会话
        if entry:
            del self.sessions[session_key]
        return None

    def resolve(self, session_key: str, valid_ids: set) -> Optional[Tuple]:
        """解析 sticky session，返回 (platform_key_id, model)；无效返回 None"""
        entry = self.get(session_key)
        if not entry:
            return None
        if entry.platform_key_id not in valid_ids:
            # 粘性 key 不在候选集内（可能已被禁用）
            return None
        return (entry.platform_key_id, entry.model)

    def unbind(self, session_key: str) -> None:
        if session_key in self.sessions:
            del self.sessions[session_key]

    def prune(self) -> int:
        """清理过期会话，返回清理数量"""
        now = time.time()
        expired = [k for k, v in self.sessions.items() if v.expires_at < now]
        for k in expired:
            del self.sessions[k]
        return len(expired)

    def count(self) -> int:
        """当前活跃会话数"""
        now = time.time()
        return sum(1 for v in self.sessions.values() if v.expires_at > now)


StickySessionManager_instance = StickySessionManager()


# ── 限流事件记录（批量异步写入）──────────────────────────────────────

async def record_request(platform_key_id: int, model: str, tokens: int = 0):
    """记录一次请求（异步批量，不阻塞）"""
    global _EVENT_BUFFER_LOCK
    if _EVENT_BUFFER_LOCK is None:
        _EVENT_BUFFER_LOCK = asyncio.Lock()

    async with _EVENT_BUFFER_LOCK:
        key = (platform_key_id, model)
        if key not in _EVENT_BUFFER:
            _EVENT_BUFFER[key] = {"request": 0, "token": 0, "ts": time.time()}
        _EVENT_BUFFER[key]["request"] += 1
        _EVENT_BUFFER[key]["token"] += tokens
        _EVENT_BUFFER[key]["ts"] = time.time()

    # 更新内存滑动窗口
    if platform_key_id in _PLATFORM_KEY_STATE:
        sw = _PLATFORM_KEY_STATE[platform_key_id].get_window(model)
        sw.add(tokens)


async def _flush_events_to_db():
    """每 5 秒把缓冲区刷入 SQLite"""
    from app.models import RateLimitEvent
    from datetime import datetime, timezone

    global _EVENT_BUFFER_LOCK
    async with _EVENT_BUFFER_LOCK:
        if not _EVENT_BUFFER:
            return
        events = dict(_EVENT_BUFFER)
        _EVENT_BUFFER.clear()

    async with async_session() as s:
        for (platform_key_id, model), data in events.items():
            # 记录请求事件
            if data["request"] > 0:
                s.add(RateLimitEvent(
                    platform_key_id=platform_key_id,
                    model=model,
                    event_type="request",
                    event_value=data["request"],
                ))
            # 记录 token 事件
            if data["token"] > 0:
                s.add(RateLimitEvent(
                    platform_key_id=platform_key_id,
                    model=model,
                    event_type="token",
                    event_value=data["token"],
                ))
        await s.commit()


async def _cleanup_old_events():
    """每小时清理 48h 前的限流记录"""
    from app.models import RateLimitEvent
    async with async_session() as s:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        await s.execute(
            delete(RateLimitEvent).where(RateLimitEvent.created_at < cutoff)
        )
        await s.commit()


# ── 启动时恢复 ─────────────────────────────────────────────────────

async def _restore_cooldowns():
    """启动时从 DB 恢复未过期的冷却（针对 PlatformKey）"""
    from app.models import PlatformKeyCooldown
    from app.models import PlatformKey
    from app.models import Platform

    async with async_session() as s:
        result = await s.execute(
            select(
                PlatformKeyCooldown.platform_key_id,
                PlatformKeyCooldown.cooldown_until,
                PlatformKeyCooldown.strike_count,
                PlatformKeyCooldown.reason,
                PlatformKey.api_key,
                PlatformKey.platform_id,
                Platform.name,
            )
            .join(PlatformKey, PlatformKeyCooldown.platform_key_id == PlatformKey.id)
            .join(Platform, PlatformKey.platform_id == Platform.id)
            .where(PlatformKeyCooldown.cooldown_until > datetime.now(timezone.utc))
        )
        for row in result:
            pk_id, cooldown_until, strike_count, reason, api_key, platform_id, platform_name = row
            state = PlatformKeyHealthState(
                platform_key_id=pk_id,
                platform_id=platform_id,
                key_label=f"Key {pk_id}",
                cooldown_until=cooldown_until.timestamp(),
                strike_count=strike_count,
            )
            register_platform_key_state(state)


async def _restore_windows():
    """启动时从 DB 恢复最近 24h 的滑动窗口（针对 PlatformKey）"""
    from app.models import RateLimitEvent
    from app.models import Platform, PlatformKey

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=86400)
    async with async_session() as s:
        # 查询最近 24h 事件
        result = await s.execute(
            select(
                RateLimitEvent.platform_key_id,
                RateLimitEvent.model,
                RateLimitEvent.event_type,
                RateLimitEvent.event_value,
                RateLimitEvent.created_at,
            ).where(RateLimitEvent.created_at >= cutoff)
        )
        rows = result.all()
        seen_ids: set = set()
        for pk_id, *_ in rows:
            seen_ids.add(pk_id)

        # 为尚未注册的 PlatformKey（如无冷却、未在 _restore_cooldowns 注册）补注册空 state，
        # 否则下方的聚合循环会因为 `_PLATFORM_KEY_STATE` 没有对应条目而丢失历史窗口。
        missing_ids = [i for i in seen_ids if i not in _PLATFORM_KEY_STATE]
        if missing_ids:
            pk_result = await s.execute(
                select(PlatformKey.id, PlatformKey.platform_id, PlatformKey.label)
                .where(PlatformKey.id.in_(missing_ids))
            )
            for pk_id, platform_id, label in pk_result:
                register_platform_key_state(PlatformKeyHealthState(
                    platform_key_id=pk_id,
                    platform_id=platform_id,
                    key_label=label or f"Key {pk_id}",
                ))

        # 按 (platform_key_id, model) 聚合事件
        agg: Dict[tuple[int, str], dict[int, list]] = {}
        for pk_id, model, evtype, value, created in rows:
            cts = created
            if cts.tzinfo is None:
                cts = cts.replace(tzinfo=timezone.utc)
            ts = cts.timestamp()
            minute_ts = int(ts // 60) * 60
            key = (pk_id, model)
            bucket_map = agg.setdefault(key, {})
            entry = bucket_map.setdefault(minute_ts, [ts, 0, 0])
            entry[0] = min(entry[0], ts)
            if evtype == "request":
                entry[1] += int(value or 0)
            elif evtype == "token":
                entry[2] += int(value or 0)

        # 填充到各 PlatformKeyHealthState 的 SlidingWindow
        total_providers = 0
        total_buckets = 0
        for (pk_id, model_key), bucket_map in agg.items():
            total_providers += 1
            sw = _PLATFORM_KEY_STATE[pk_id].get_window(model_key)
            for minute_ts in sorted(bucket_map.keys()):
                first_ts, req_sum, tok_sum = bucket_map[minute_ts]
                sw._buckets.append(MinuteBucket(
                    ts=first_ts,
                    request_count=req_sum,
                    token_count=tok_sum,
                ))
                total_buckets += 1

        print(f"[health] restored sliding windows: {total_providers} platform_keys, {total_buckets} minute-buckets")


async def _persist_cooldowns():
    """定期把内存冷却状态写回 DB"""
    from app.models import PlatformKeyCooldown
    from datetime import datetime, timezone

    async with async_session() as s:
        for pk_id, state in _PLATFORM_KEY_STATE.items():
            if state.cooldown_until is None or state.cooldown_until <= time.time():
                # 已过期，删除 DB 记录
                await s.execute(
                    delete(PlatformKeyCooldown).where(PlatformKeyCooldown.platform_key_id == pk_id)
                )
            else:
                # 保存冷却状态
                existing = await s.execute(
                    select(PlatformKeyCooldown).where(PlatformKeyCooldown.platform_key_id == pk_id)
                )
                row = existing.scalar_one_or_none()
                cooldown_until = datetime.fromtimestamp(state.cooldown_until, tz=timezone.utc)
                if row:
                    row.cooldown_until = cooldown_until
                    row.strike_count = state.strike_count
                else:
                    s.add(PlatformKeyCooldown(
                        platform_key_id=pk_id,
                        cooldown_until=cooldown_until,
                        strike_count=state.strike_count,
                        reason="rate_limit",
                    ))
        await s.commit()


async def _bg_flusher():
    while True:
        await asyncio.sleep(_FLUSH_INTERVAL)
        try:
            await _flush_events_to_db()
        except Exception:
            pass


async def _bg_cooldown_persister():
    while True:
        await asyncio.sleep(_FLUSH_INTERVAL * 2)  # 10s
        try:
            await _persist_cooldowns()
        except Exception:
            pass


async def _decay_penalties():
    """每 2 分钟，所有 PlatformKey 惩罚分 -1"""
    for state in _PLATFORM_KEY_STATE.values():
        state.decay_penalty()


async def _bg_penalty_decay():
    while True:
        await asyncio.sleep(_PENALTY_DECAY_INTERVAL)
        try:
            await _decay_penalties()
        except Exception:
            pass


async def _bg_cleanup():
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        try:
            await _cleanup_old_events()
            StickySessionManager_instance.prune()
        except Exception:
            pass


async def start_health_tasks():
    """启动所有后台任务（在 FastAPI lifespan startup 时调用）"""
    global _EVENT_BUFFER_LOCK
    if _EVENT_BUFFER_LOCK is None:
        _EVENT_BUFFER_LOCK = asyncio.Lock()

    # 预注册所有 PlatformKeys + 活跃 PoolItem 的 state（TODO: 实现 _register_all_platform_keys）
    # 暂时先空实现，等待 pool_router.py 更新后调用注册

    await _restore_cooldowns()
    await _restore_windows()
    _BACKGROUND_TASKS.extend([
        asyncio.create_task(_bg_flusher(), name="health_flusher"),
        asyncio.create_task(_bg_cooldown_persister(), name="health_cooldown_persister"),
        asyncio.create_task(_bg_penalty_decay(), name="health_penalty_decay"),
        asyncio.create_task(_bg_cleanup(), name="health_cleanup"),
    ])


async def stop_health_tasks():
    """停止后台任务（在 FastAPI lifespan shutdown 时调用）"""
    for t in _BACKGROUND_TASKS:
        t.cancel()
    await asyncio.gather(*_BACKGROUND_TASKS, return_exceptions=True)
    _BACKGROUND_TASKS.clear()
    try:
        await _flush_events_to_db()
        await _persist_cooldowns()
    except Exception:
        pass