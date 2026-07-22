"""代理服务 - 转发客户端请求到上游 Provider

增强功能：
- 自动路由 + 故障转移（429/5xx 自动回退，最多 N 次）
- 滑动窗口限流（4 维度，异步批量写入）
- 冷却升级策略（429 指数增长）
- 动态惩罚路由（429 时 +3，每 2 分钟 -1）
- Sticky Session（多轮对话 30 分钟粘性）

响应头：
- X-Fallback-Attempts: 回退尝试次数
- X-Routed-Via: 实际调用的 provider (id / model)
"""
import time
import json
import uuid
from datetime import datetime
from typing import Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.config import settings
from app.models import ClientKey, Pool, PoolItem, Provider, RequestLog
from app.services.pool_router import PoolRouter
from app.services import provider_health as ph


def _ensure_provider_state(item: PoolItem):
    """确保 provider 已注册到 health 系统"""
    if not item.provider:
        return
    state = ph.get_provider_state(item.provider.id)
    if state is None:
        state = ph.ProviderState(
            provider_id=item.provider.id,
            provider_name=item.provider.name,
            base_url=item.provider.base_url,
            is_active=item.provider.is_active,
            base_priority=item.priority,
        )
        ph.register_provider(state)


async def authenticate_client(
    session: AsyncSession,
    authorization: str,
) -> Optional[ClientKey]:
    """校验客户端 key：Authorization: Bearer sk-xxx"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    key_str = authorization[7:]
    q = (
        select(ClientKey)
        .options(selectinload(ClientKey.pool).selectinload(Pool.pool_items).selectinload(PoolItem.provider))
        .where(ClientKey.key == key_str)
    )
    key_obj = (await session.execute(q)).scalar_one_or_none()
    if not key_obj or not key_obj.is_active:
        return None
    return key_obj


def check_model_allowed(client_key: ClientKey, model: str) -> bool:
    """校验 client key 是否有权调用某个 model"""
    if not client_key.allowed_models:
        return True
    return model in client_key.allowed_models


def resolve_pool_for_key(client_key: ClientKey, model: str) -> Optional[Pool]:
    """从 client_key 绑定的 pool 找到实际的 Pool 实例（model 过滤在 get_ordered_items 中做）"""
    pool = client_key.pool
    if not pool or not pool.is_active:
        return None
    return pool


async def get_ordered_items(
    pool: Pool,
    strategy: str,
    sticky_provider_id: Optional[int] = None,
) -> Tuple[list, int]:
    """
    获取按策略排序的候选 PoolItem 列表（健康感知）。
    上游转发时用 pool_item.model（如为空则用客户端请求的 model）。
    """
    # 不做 model 过滤 —— 所有 active pool_items 都是候选
    # pool_item.model 决定转发给上游时用哪个模型
    router = PoolRouter(list(pool.pool_items))
    items, fallback_count = router.select_all_routable(strategy, sticky_provider_id)
    # 确保所有 provider 已注册
    for item in items:
        _ensure_provider_state(item)
    return items, fallback_count


def is_multi_turn(messages: list) -> bool:
    """判断是否是多轮对话"""
    return any(m.get("role") == "assistant" for m in messages)


def make_session_key(ip: str, first_user_message: str) -> str:
    """生成 Sticky Session key"""
    return StickySessionManager.make_key(ip, first_user_message)


# ── 核心代理逻辑 ──────────────────────────────────────────────────
async def proxy_json_request(
    pool: Pool,
    body: dict,
    sticky_provider_id: Optional[int] = None,
) -> tuple:
    """非流式代理（增强版：限流/冷却/惩罚路由）"""
    start = time.time()
    ordered, fallback_count = await get_ordered_items(pool, pool.strategy, sticky_provider_id)

    last_error = ""
    last_provider_id = None
    last_provider_model = None

    for item in ordered:
        if not item.provider or not item.provider.is_active:
            continue
        upstream_url = f"{item.provider.base_url.rstrip('/')}/chat/completions"
        upstream_body = {
            **body,
            "model": item.model or body.get("model", ""),
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.UPSTREAM_TIMEOUT) as client:
                t0 = time.time()
                resp = await client.post(
                    upstream_url,
                    json=upstream_body,
                    headers={
                        "Authorization": f"Bearer {item.provider.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                ttft = (time.time() - t0) * 1000
                last_provider_id = item.provider.id
                last_provider_model = item.model

                if resp.status_code == 200:
                    # 成功
                    state = ph.get_provider_state(item.provider.id)
                    if state:
                        state.record_success()
                    data = resp.json()
                    usage = data.get("usage", {}) or {}
                    pt = usage.get("prompt_tokens", 0)
                    ct = usage.get("completion_tokens", 0)
                    total = pt + ct
                    if total > 0:
                        await ph.record_request(item.provider.id, item.model, total)
                    return (
                        200,
                        data,
                        _make_meta(
                            item, fallback_count, start,
                            pt=pt, ct=ct, ttft=ttft,
                        ),
                    )
                elif resp.status_code == 429:
                    # 429：触发惩罚 + 冷却 + 限流记录
                    state = ph.get_provider_state(item.provider.id)
                    if state:
                        dur = state.record_429()
                    await ph.record_request(item.provider.id, item.model, tokens=0)
                    last_error = f"Upstream 429 from {item.provider.name} -> cooldown {int(dur.total_seconds()) if 'dur' in dir() else '?'}s"
                    continue
                else:
                    last_error = f"Upstream {resp.status_code} from {item.provider.name}"
                    continue
        except httpx.TimeoutException:
            last_error = f"Timeout from {item.provider.name}"
        except Exception as e:
            last_error = f"{item.provider.name} error: {str(e)}"

    # 所有尝试都失败
    return 502, {"error": {"message": f"All upstreams failed: {last_error}"}}, _make_meta_fail(
        last_provider_id, last_provider_model, fallback_count, start, last_error
    )


async def proxy_stream_request(
    pool: Pool,
    body: dict,
    sticky_provider_id: Optional[int] = None,
) -> tuple:
    """流式代理（增强版）"""
    start = time.time()
    ordered, fallback_count = await get_ordered_items(pool, pool.strategy, sticky_provider_id)

    last_error = ""
    last_provider_id = None
    last_provider_model = None

    for item in ordered:
        if not item.provider or not item.provider.is_active:
            continue
        upstream_url = f"{item.provider.base_url.rstrip('/')}/chat/completions"
        upstream_body = {
            **body,
            "model": item.model or body.get("model", ""),
            "stream": True,
        }

        try:
            t0 = time.time()
            client = httpx.AsyncClient(timeout=settings.UPSTREAM_TIMEOUT)
            resp = await client.send(
                client.build_request(
                    "POST", upstream_url,
                    json=upstream_body,
                    headers={
                        "Authorization": f"Bearer {item.provider.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                ),
                stream=True,
            )
            ttft = (time.time() - t0) * 1000
            last_provider_id = item.provider.id
            last_provider_model = item.model

            if resp.status_code == 200:
                chosen_item_id = item.id
                chosen_provider_id = item.provider.id
                meta_container: dict = {}
                meta_container_ref = meta_container

                async def gen():
                    last_usage = {}
                    completion_tokens = 0
                    try:
                        async for chunk in resp.aiter_bytes():
                            for line in chunk.decode("utf-8", errors="replace").split("\n"):
                                if line.startswith("data: "):
                                    payload = line[6:].strip()
                                    if payload and payload != "[DONE]":
                                        try:
                                            obj = json.loads(payload)
                                            u = obj.get("usage", {})
                                            if u:
                                                last_usage = u
                                            # 累计 completion tokens（每个 delta 的 content 字符数累加）
                                            deltas = obj.get("choices", [{}])
                                            for choice in deltas:
                                                delta = choice.get("delta", {})
                                                if delta.get("content"):
                                                    completion_tokens += len(delta["content"])
                                        except json.JSONDecodeError:
                                            pass
                            yield chunk
                    finally:
                        await resp.aclose()
                        await client.aclose()
                        # 从最后一条 usage 提取 token 数（流式只在最后 chunk 返回）
                        total = last_usage.get("total_tokens", 0)
                        pt = last_usage.get("prompt_tokens")
                        if pt is None:
                            # 总 tokens 已知时反推 prompt_tokens
                            ct_from_usage = last_usage.get("completion_tokens", 0)
                            pt = max(0, total - ct_from_usage) if total else 0
                        ct = last_usage.get("completion_tokens") or completion_tokens
                        meta_container_ref.update(_make_meta(
                            item, fallback_count, start,
                            pt=pt, ct=ct, ttft=ttft,
                        ))

                return 200, gen(), meta_container
            elif resp.status_code == 429:
                state = ph.get_provider_state(item.provider.id)
                if state:
                    dur = state.record_429()
                await ph.record_request(item.provider.id, item.model, tokens=0)
                last_error = f"Upstream 429 from {item.provider.name}"
                await resp.aread()
                await resp.aclose()
                await client.aclose()
                continue
            else:
                await resp.aread()
                await resp.aclose()
                await client.aclose()
                last_error = f"Upstream {resp.status_code} from {item.provider.name}"
                continue
        except httpx.TimeoutException:
            last_error = f"Timeout from {item.provider.name}"
        except Exception as e:
            last_error = f"{item.provider.name} error: {str(e)}"

    return 502, None, None


def _make_meta(
    item: PoolItem,
    fallback_count: int,
    start: float,
    pt: int = 0,
    ct: int = 0,
    ttft: float = 0,
    error: str = "",
) -> dict:
    return {
        "pool_item_id": item.id,
        "provider_id": item.provider.id,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "latency_ms": (time.time() - start) * 1000,
        "ttft_ms": ttft,
        "error": error,
        "headers": {
            "X-Fallback-Attempts": str(fallback_count),
            "X-Routed-Via": f"{item.provider.id} ({item.model})",
        },
    }


def _make_meta_fail(
    provider_id: Optional[int],
    model: Optional[str],
    fallback_count: int,
    start: float,
    error: str,
) -> dict:
    return {
        "pool_item_id": None,
        "provider_id": provider_id,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": (time.time() - start) * 1000,
        "ttft_ms": 0,
        "error": error,
        "headers": {
            "X-Fallback-Attempts": str(fallback_count),
            "X-Routed-Via": f"{provider_id} ({model})" if provider_id else "",
        },
    }


def make_log(
    client_key_id: Optional[int],
    model: str,
    request_id: str,
    status: str,
    meta: dict,
    ip: str = "",
    ua: str = "",
    request_body: str = "",
    response_body: str = "",
    is_stream: bool = False,
) -> RequestLog:
    return RequestLog(
        client_key_id=client_key_id,
        pool_item_id=meta.get("pool_item_id"),
        provider_id=meta.get("provider_id"),
        model=model,
        request_id=request_id,
        status=status,
        prompt_tokens=meta.get("prompt_tokens", 0),
        completion_tokens=meta.get("completion_tokens", 0),
        total_tokens=meta.get("total_tokens", 0),
        latency_ms=meta.get("latency_ms", 0),
        ttft_ms=meta.get("ttft_ms", 0),
        error_message=meta.get("error", ""),
        ip_address=ip,
        user_agent=ua,
        request_body=request_body,
        response_body=response_body,
        is_stream=is_stream,
    )


async def increment_key_usage(client_key_id: int, total_tokens: int):
    """独立 session 写：避免原 request session 已关"""
    async with async_session() as s:
        key_obj = await s.get(ClientKey, client_key_id)
        if key_obj:
            key_obj.request_count += 1
            key_obj.total_tokens += total_tokens
            key_obj.last_used_at = datetime.now()
            await s.commit()


async def list_available_models(session: AsyncSession) -> list:
    """列出所有 active 的 Pool 名（作为 /v1/models 返回）"""
    q = select(Pool).where(Pool.is_active == True).order_by(Pool.name)
    pools = (await session.execute(q)).scalars().all()
    return [
        {"id": p.name, "object": "model", "owned_by": "ai-gateway"}
        for p in pools
    ]


# ── Sticky Session Manager 简单包装 ────────────────────────────────
class StickySessionManager:
    @staticmethod
    def make_key(ip: str, first_user_message: str) -> str:
        return ph.StickySessionManager_instance.make_key(ip, first_user_message)

    @staticmethod
    def bind(key: str, provider_id: int, model: str):
        ph.StickySessionManager_instance.bind(key, provider_id, model)

    @staticmethod
    def resolve(key: str, valid_provider_ids: set[int]) -> Optional[Tuple[int, str]]:
        return ph.StickySessionManager_instance.resolve(key, valid_provider_ids)

    @staticmethod
    def count() -> int:
        return ph.StickySessionManager_instance.count()