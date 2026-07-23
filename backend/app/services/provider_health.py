"""Provider Health - 限流 / 冷却 / 惩罚路由 / Sticky Session

核心概念：
- SlidingWindow: 维护每分钟的请求数和 token 数的汇总（每分钟一条，1440 条 = 24h）
- CooldownManager: Provider 冷却状态，429 时触发，指数增长冷却时间
- PenaltyManager: 惩罚分，429 时 +3，每 2 分钟 -1
- StickySessionManager: 多轮对话粘性，绑定 provider_id+model，TTL 30min
- ProviderHealthService: 整合以上组件 + 启动后台任务（flusher / penalty_decay）
"""
import asyncio
import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, delete, func as sql_func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session


# ── 冷却升级时间表 ──────────────────────────────────────────────
_COOLDOWN_LEVELS = [
    timedelta(minutes=2),   # strike=1
    timedelta(minutes=10),  # strike=2
    timedelta(hours=1),     # strike=3
    timedelta(hours=24),    # strike>=4
]
_MAX_STRIKE = len(_COOLDOWN_LEVELS)


def _cooldown_for_strike(strike: int) -> timedelta:
    idx = min(strike - 1, _MAX_STRIKE - 1)
    return _COOLDOWN_LEVELS[idx]


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
    维护一个 24h 的滑动窗口，每分钟一条汇总记录。
    - rpm / tpm: 仅看过去 60s
    - rpd / tpd: 全部 86400s
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
        now = time.time()
        now_min = int(now // 60) * 60.0
        if self._buckets and abs(self._buckets[-1].ts - now_min) < 1e-6:
            # 同一分钟，合并到该 bucket（首条请求的时间戳保留）
            self._buckets[-1].request_count += 1
            self._buckets[-1].token_count += token_count
        else:
            # 新分钟，新建 bucket，时间戳用请求实际时刻
            self._buckets.append(MinuteBucket(ts=now, request_count=1, token_count=token_count))

    def _get_buckets_under(self, window_seconds: float) -> list:
        """返回窗口内的所有 bucket，清除过期数据"""
        cutoff = time.time() - window_seconds
        while self._buckets and self._buckets[0].ts < cutoff:
            self._buckets.popleft()
        return list(self._buckets)

    def count(self, window_seconds: float) -> int:
        return sum(b.request_count for b in self._get_buckets_under(window_seconds))

    def tokens(self, window_seconds: float) -> int:
        return sum(b.token_count for b in self._get_buckets_under(window_seconds))

    def to_snapshot(self) -> dict:
        """序列化，用于 DB flush"""
        return {
            "buckets": [(b.ts, b.request_count, b.token_count) for b in self._buckets]
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "SlidingWindow":
        sw = cls()
        if data:
            for ts, rc, tc in data.get("buckets", []):
                sw._buckets.append(MinuteBucket(ts=float(ts), request_count=rc, token_count=tc))
        return sw


# ── Provider Health State（内存状态）────────────────────────────
@dataclass
class ProviderState:
    """单个 Provider 的全部健康状态"""
    provider_id: int
    provider_name: str
    base_url: str
    is_active: bool
    base_priority: int = 0            # 从 pool_item.priority 来的基础优先级
    penalty_score: int = 0            # 惩罚分，0-10
    last_decay: float = field(default_factory=time.time)

    # 滑动窗口：key=(model or "")
    windows: Dict[str, SlidingWindow] = field(default_factory=dict)

    # 冷却
    cooldown_until: Optional[float] = None  # unix timestamp，无冷却时 None
    strike_count: int = 0

    # Sticky Session 绑定
    sticky_model: Optional[str] = None

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
            return 0.0
        rem = self.cooldown_until - time.time()
        return max(0.0, rem)

    def is_usable(self, model: str = "") -> Tuple[bool, str]:
        """
        判断 Provider 是否可用，返回 (可用, 原因)
        """
        if not self.is_active:
            return False, "provider_inactive"
        if self.is_in_cooldown():
            return False, f"cooldown_{int(self.cooldown_remaining())}s"
        win = self.get_window(model)
        # 4 维度检查（宽松阈值，上游 API key 的限流由上游侧控制，这里网关侧做辅助提示）
        # 这里先不做硬限流（避免误杀），只用于管理员展示
        return True, "ok"

    def effective_priority(self) -> int:
        return self.base_priority - self.penalty_score

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


# ── Sticky Session Manager ───────────────────────────────────────
@dataclass
class StickyEntry:
    provider_id: int
    model: str
    created_at: float
    expires_at: float    # now + 30min

    def valid(self) -> bool:
        return time.time() < self.expires_at


class StickySessionManager:
    TTL_SECONDS = 30 * 60   # 30 分钟

    def __init__(self):
        self._sessions: Dict[str, StickyEntry] = {}

    @staticmethod
    def make_key(ip: str, first_user_message: str) -> str:
        content = f"{ip}|{hashlib.sha1(first_user_message.encode()).hexdigest()[:16]}"
        return hashlib.sha1(content.encode()).hexdigest()[:32]

    def bind(self, key: str, provider_id: int, model: str):
        now = time.time()
        self._sessions[key] = StickyEntry(
            provider_id=provider_id,
            model=model,
            created_at=now,
            expires_at=now + self.TTL_SECONDS,
        )

    def resolve(self, key: str, valid_provider_ids: set[int]) -> Optional[Tuple[int, str]]:
        """解析 sticky key，返回 (provider_id, model) 或 None"""
        entry = self._sessions.get(key)
        if not entry or not entry.valid():
            self._sessions.pop(key, None)
            return None
        if entry.provider_id not in valid_provider_ids:
            # provider 不可用，清除粘性
            self._sessions.pop(key, None)
            return None
        return entry.provider_id, entry.model

    def prune(self):
        """清理过期 session"""
        now = time.time()
        self._sessions = {k: v for k, v in self._sessions.items() if v.expires_at > now}

    def count(self) -> int:
        return len(self._sessions)


# ── Main Service ─────────────────────────────────────────────────
_PROVIDER_STATE: Dict[int, ProviderState] = {}
_PENALTY_DECAY_INTERVAL = 120   # 2 分钟
_FLUSH_INTERVAL = 5             # 5 秒
_CLEANUP_INTERVAL = 3600       # 1 小时
_BACKGROUND_TASKS: List[asyncio.Task] = []


def get_provider_state(provider_id: int) -> Optional[ProviderState]:
    return _PROVIDER_STATE.get(provider_id)


def register_provider(state: ProviderState):
    _PROVIDER_STATE[state.provider_id] = state


def clear_providers():
    _PROVIDER_STATE.clear()


def get_all_states() -> Dict[int, ProviderState]:
    return dict(_PROVIDER_STATE)


# ── 限流事件缓冲（批量写入）────────────────────────────────────
_event_buffer: Dict[Tuple[int, str], dict] = {}   # (provider_id, model) → {"request": N, "token": N}
_EVENT_BUFFER_LOCK = asyncio.Lock()


async def record_request(provider_id: int, model: str, tokens: int = 0):
    """记录一次请求（异步批量，不阻塞）"""
    async with _EVENT_BUFFER_LOCK:
        key = (provider_id, model)
        if key not in _event_buffer:
            _event_buffer[key] = {"request": 0, "token": 0, "ts": time.time()}
        _event_buffer[key]["request"] += 1
        _event_buffer[key]["token"] += tokens
        _event_buffer[key]["ts"] = time.time()

    # 更新内存滑动窗口
    if provider_id in _PROVIDER_STATE:
        sw = _PROVIDER_STATE[provider_id].get_window(model)
        sw.add(tokens)


async def _flush_events_to_db():
    """每 5 秒把缓冲区刷入 SQLite"""
    async with _EVENT_BUFFER_LOCK:
        if not _event_buffer:
            return
        events = dict(_event_buffer)
        _event_buffer.clear()

    async with async_session() as s:
        from app.models import RateLimitEvent
        now = datetime.now(timezone.utc)
        records = [
            RateLimitEvent(
                provider_id=pid,
                model=mid,
                event_type="request",
                event_value=ev["request"],
                created_at=now,
            )
            for (pid, mid), ev in events.items()
            if ev.get("request", 0) > 0
        ]
        token_records = [
            RateLimitEvent(
                provider_id=pid,
                model=mid,
                event_type="token",
                event_value=ev["token"],
                created_at=now,
            )
            for (pid, mid), ev in events.items()
            if ev.get("token", 0) > 0
        ]
        if records or token_records:
            s.add_all(records + token_records)
            await s.commit()


async def _cleanup_old_events():
    """每小时清理 48h 前的限流记录"""
    async with async_session() as s:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        await s.execute(
            delete(RateLimitEvent).where(RateLimitEvent.created_at < cutoff)
        )
        await s.commit()


async def _decay_penalties():
    """每 2 分钟，所有 Provider 惩罚分 -1"""
    for state in _PROVIDER_STATE.values():
        state.decay_penalty()


async def _restore_cooldowns():
    """启动时从 DB 恢复未过期的冷却"""
    from app.models import ProviderCooldown
    async with async_session() as s:
        result = await s.execute(
            select(ProviderCooldown).where(
                ProviderCooldown.cooldown_until > datetime.now(timezone.utc)
            )
        )
        for row in result.scalars().all():
            if row.provider_id in _PROVIDER_STATE:
                st = _PROVIDER_STATE[row.provider_id]
                st.cooldown_until = row.cooldown_until.timestamp()
                st.strike_count = row.strike_count


async def _register_all_providers():
    """启动时预注册所有 Provider + 活跃 PoolItem 到 _PROVIDER_STATE。

    这样 _restore_windows 才能把 DB 中的历史事件填进对应 Provider 的滑动窗口。
    （运行时是懒注册的，但那已经在请求进来了才发生，错过了启动时的批量恢复。）
    """
    from app.models import Provider, PoolItem, Pool
    async with async_session() as s:
        # 查所有 Provider 及其活跃 PoolItem（含 priority）
        rows = (await s.execute(
            select(Provider, PoolItem, Pool)
            .join(PoolItem, PoolItem.provider_id == Provider.id)
            .join(Pool, PoolItem.pool_id == Pool.id)
            .where(PoolItem.is_active == True, Provider.is_active == True)
        )).all()
        for provider, pool_item, pool in rows:
            if provider.id not in _PROVIDER_STATE:
                _PROVIDER_STATE[provider.id] = ProviderState(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    base_url=provider.base_url,
                    is_active=provider.is_active,
                    base_priority=pool_item.priority,
                )
            else:
                # 已存在的 state 保留运行时累积的状态（不覆盖）
                pass


async def _restore_windows():
    """启动时从 rate_limit_events 表回放最近 24h 事件，重填各 Provider 的滑动窗口。

    保证容器重启后 RPD/TPD 不会归零。每分钟聚合成一个 bucket（与运行时行为一致），
    bucket 时间戳 = 该分钟内首条事件的时间。
    """
    from app.models import RateLimitEvent
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=86400)
    async with async_session() as s:
        result = await s.execute(
            select(
                RateLimitEvent.provider_id,
                RateLimitEvent.model,
                RateLimitEvent.event_type,
                RateLimitEvent.event_value,
                RateLimitEvent.created_at,
            ).where(RateLimitEvent.created_at >= cutoff)
        )
        # 按 (provider_id, model, minute) 聚合：request 求和、token 求和
        # 每分钟只造一个 bucket，时间戳 = 该分钟内首条事件的真实时间
        # 结构: {(pid, model): {minute_ts: [first_event_ts, req_sum, tok_sum]}}
        agg: Dict[Tuple[int, str], Dict[int, list]] = {}
        for pid, model, evtype, value, created in result.all():
            if pid not in _PROVIDER_STATE:
                continue
            if created is None:
                continue
            # created 可能带 tz（UTC），统一转 unix ts
            cts = created
            if cts.tzinfo is None:
                cts = cts.replace(tzinfo=timezone.utc)
            ts = cts.timestamp()
            minute_ts = int(ts // 60) * 60
            key = (pid, model or "")
            bucket_map = agg.setdefault(key, {})
            entry = bucket_map.setdefault(minute_ts, [ts, 0, 0])  # [first_ts, req_sum, tok_sum]
            entry[0] = min(entry[0], ts)  # 该分钟内最早事件时间
            if evtype == "request":
                entry[1] += int(value or 0)
            elif evtype == "token":
                entry[2] += int(value or 0)

        # 填充到各 Provider 的 SlidingWindow
        for (pid, model), bucket_map in agg.items():
            if pid not in _PROVIDER_STATE:
                continue
            sw = _PROVIDER_STATE[pid].get_window(model)
            # 按时间升序填充
            for minute_ts in sorted(bucket_map.keys()):
                first_ts, req_sum, tok_sum = bucket_map[minute_ts]
                sw._buckets.append(MinuteBucket(
                    ts=first_ts,
                    request_count=req_sum,
                    token_count=tok_sum,
                ))

        # 统计日志
        total_buckets = sum(len(bm) for bm in agg.values())
        providers_restored = len({pid for (pid, _) in agg.keys()})
        print(f"[health] restored sliding windows: {providers_restored} providers, {total_buckets} minute-buckets")


async def _persist_cooldowns():
    """定期把内存冷却状态写回 DB"""
    from app.models import ProviderCooldown
    async with async_session() as s:
        now = datetime.now(timezone.utc)
        for state in _PROVIDER_STATE.values():
            if state.cooldown_until is not None and state.cooldown_until > time.time():
                # 更新或插入
                row = await s.get(ProviderCooldown, state.provider_id)
                if row:
                    row.cooldown_until = datetime.fromtimestamp(state.cooldown_until, tz=timezone.utc)
                    row.strike_count = state.strike_count
                    row.updated_at = now
                else:
                    s.add(ProviderCooldown(
                        provider_id=state.provider_id,
                        cooldown_until=datetime.fromtimestamp(state.cooldown_until, tz=timezone.utc),
                        strike_count=state.strike_count,
                        reason="rate_limit",
                        updated_at=now,
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
        await asyncio.sleep(30)
        try:
            await _persist_cooldowns()
        except Exception:
            pass


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


# ── 全局单例 ─────────────────────────────────────────────────────
StickySessionManager_instance = StickySessionManager()


async def start_health_tasks():
    """启动所有后台任务（在 FastAPI lifespan startup 时调用）"""
    # 预注册所有 Provider + 活跃 PoolItem 的 state，让后续 _restore_windows 能找到 PID
    await _register_all_providers()
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
    # shutdown 前 flush 最后一次
    try:
        await _flush_events_to_db()
        await _persist_cooldowns()
    except Exception:
        pass