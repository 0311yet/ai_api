"""
代理服务 - 转发客户端请求到上游 PlatformKey

增强功能：
- 自动路由 + 故障转移（429/5xx 自动回退，最多 N 次）
- 滑动窗口限流（4 维度，异步批量写入）
- 冷却升级策略（429 指数增长）
- 动态惩罚路由（429 时 +3，每 2 分钟 -1）
- Sticky Session（多轮对话 30 分钟粘性）
- **同 Platform 下 Key 级回退**（429 时切换同一 Platform 的其他 Keys）

响应头：
- X-Fallback-Attempts: 回退尝试次数
- X-Routed-Via: 实际调用的 PlatformKey (platform_id/key_id/model)
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
from app.models import ClientKey, Pool, PoolItem, Platform, PlatformKey, RequestLog
from app.services.pool_router import PoolRouter
from app.services import provider_health as ph


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
        .options(
            selectinload(ClientKey.pool)
            .selectinload(Pool.pool_items)
            .selectinload(PoolItem.platform)
            .selectinload(Platform.platform_keys)
        )
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
    """从 client_key 绑定的 pool 找到实际的 Pool 实例"""
    pool = client_key.pool
    if not pool or not pool.is_active:
        return None
    return pool


async def get_ordered_items(
    pool: Pool,
    strategy: str,
    sticky_platform_key_id: Optional[int] = None,
) -> Tuple[list, int]:
    """
    获取按策略排序的候选 PoolItem 列表（健康感知）
    每个 PoolItem 会被展开为多个 RoutableItem（同一 Platform 的多个 Keys）
    """
    # 使用 PoolRouter 的 get_routable_items 获取所有 PoolItem + PlatformKeys
    from app.services.pool_router import get_routable_items
    items, fallback_count = await get_routable_items(
        pool.id,
        model="",
        sticky_platform_key_id=sticky_platform_key_id,
    )
    return items, fallback_count


def is_multi_turn(messages: list) -> bool:
    """判断是否是多轮对话"""
    return any(m.get("role") == "assistant" for m in messages)


def make_session_key(ip: str, first_user_message: str) -> str:
    """生成 Sticky Session key"""
    return ph.StickySessionManager.make_key(ip, first_user_message)


# ── 核心代理逻辑 ──────────────────────────────────────────────────

async def proxy_json_request(
    pool: Pool,
    body: dict,
    sticky_platform_key_id: Optional[int] = None,
) -> tuple:
    """非流式代理（增强版：限流/冷却/惩罚路由 + Key 级回退）"""
    start = time.time()
    ordered, fallback_count = await get_ordered_items(pool, pool.strategy, sticky_platform_key_id)

    last_error = ""
    last_platform_key_id = None
    last_provider_id = None
    last_provider_model = None

    for pool_item in ordered:
        platform_key_id = pool_item.platform_key_id
        state = ph.get_platform_key_state(platform_key_id)
        if not state:
            # 无状态（不应发生），创建默认状态
            state = ph.PlatformKeyHealthState(
                platform_key_id=platform_key_id,
                platform_id=pool_item.platform_id,
                key_label=pool_item.key_label,
            )
            ph.register_platform_key_state(state)

        # 检查该 key 是否可用（冷却/健康状态）
        can_serve, reason = state.can_serve(pool_item.model)
        if not can_serve:
            last_error = f"{state.key_label} (key {platform_key_id}) is {reason}"
            continue

        # 使用该 key 调用上游
        upstream_url = f"{pool_item.base_url.rstrip('/')}/chat/completions"
        upstream_body = {
            **body,
            "model": pool_item.model or body.get("model", ""),
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.UPSTREAM_TIMEOUT) as client:
                t0 = time.time()
                resp = await client.post(
                    upstream_url,
                    json=upstream_body,
                    headers={
                        "Authorization": f"Bearer {pool_item.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                ttft = (time.time() - t0) * 1000
                last_platform_key_id = platform_key_id
                last_provider_id = pool_item.platform_id
                last_provider_model = pool_item.model

                if resp.status_code == 200:
                    # 成功
                    state.record_success()
                    data = resp.json()
                    usage = data.get("usage", {}) or {}
                    pt = usage.get("prompt_tokens", 0)
                    ct = usage.get("completion_tokens", 0)
                    total = pt + ct
                    if total > 0:
                        await ph.record_request(platform_key_id, pool_item.model, total)
                    return (
                        200,
                        data,
                        _make_meta(
                            pool_item, platform_key_id,
                            fallback_count, start,
                            pt=pt, ct=ct, ttft=ttft,
                        ),
                    )
                elif resp.status_code == 429:
                    # 429：触发惩罚 + 冷却
                    dur = state.record_429()
                    await ph.record_request(platform_key_id, pool_item.model, tokens=0)
                    last_error = f"{state.key_label} (key {platform_key_id}) is in cooldown ({int(dur.total_seconds()) if hasattr(dur, 'total_seconds') else int(dur)}s)"
                    continue
                else:
                    last_error = f"{pool_item.key_label} (key {platform_key_id}) upstream {resp.status_code}"
                    continue
        except httpx.TimeoutException:
            last_error = f"{pool_item.key_label} (key {platform_key_id}) timeout"
        except Exception as e:
            last_error = f"{pool_item.key_label} (key {platform_key_id}) error: {str(e)}"

    # 所有尝试都失败
    return 502, {"error": {"message": f"All upstreams failed: {last_error}"}}, _make_meta_fail(
        last_provider_id, last_provider_model, fallback_count, start, last_error
    )


async def proxy_stream_request(
    pool: Pool,
    body: dict,
    sticky_platform_key_id: Optional[int] = None,
) -> tuple:
    """流式代理（增强版 + Key 级回退）"""
    start = time.time()
    ordered, fallback_count = await get_ordered_items(pool, pool.strategy, sticky_platform_key_id)

    last_error = ""
    last_platform_key_id = None
    last_provider_id = None
    last_provider_model = None

    for pool_item in ordered:
        platform_key_id = pool_item.platform_key_id
        state = ph.get_platform_key_state(platform_key_id)
        if not state:
            state = ph.PlatformKeyHealthState(
                platform_key_id=platform_key_id,
                platform_id=pool_item.platform_id,
                key_label=pool_item.key_label,
            )
            ph.register_platform_key_state(state)

        can_serve, reason = state.can_serve(pool_item.model)
        if not can_serve:
            last_error = f"{state.key_label} (key {platform_key_id}) is {reason}"
            continue

        upstream_url = f"{pool_item.base_url.rstrip('/')}/chat/completions"
        upstream_body = {
            **body,
            "model": pool_item.model or body.get("model", ""),
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
                        "Authorization": f"Bearer {pool_item.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                ),
                stream=True,
            )
            ttft = (time.time() - t0) * 1000
            last_platform_key_id = platform_key_id
            last_provider_id = pool_item.platform_id
            last_provider_model = pool_item.model

            if resp.status_code == 200:
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
                        total = last_usage.get("total_tokens", 0)
                        pt = last_usage.get("prompt_tokens")
                        if pt is None:
                            ct_from_usage = last_usage.get("completion_tokens", 0)
                            pt = max(0, total - ct_from_usage) if total else 0
                        ct = last_usage.get("completion_tokens") or completion_tokens
                        meta_container_ref.update(_make_meta(
                            pool_item, platform_key_id,
                            fallback_count, start,
                            pt=pt, ct=ct, ttft=ttft,
                        ))

                return 200, gen(), meta_container
            elif resp.status_code == 429:
                dur = state.record_429()
                await ph.record_request(platform_key_id, pool_item.model, tokens=0)
                last_error = f"{state.key_label} (key {platform_key_id}) is in cooldown"
                await resp.aread()
                await resp.aclose()
                await client.aclose()
                continue
            else:
                await resp.aread()
                await resp.aclose()
                await client.aclose()
                last_error = f"{pool_item.key_label} (key {platform_key_id}) upstream {resp.status_code}"
                continue
        except httpx.TimeoutException:
            last_error = f"{pool_item.key_label} (key {platform_key_id}) timeout"
        except Exception as e:
            last_error = f"{pool_item.key_label} (key {platform_key_id}) error: {str(e)}"

    return 502, None, None


def _make_meta(
    pool_item,
    platform_key_id: int,
    fallback_count: int,
    start: float,
    pt: int = 0,
    ct: int = 0,
    ttft: float = 0,
    error: str = "",
) -> dict:
    return {
        "pool_item_id": pool_item.pool_item_id if hasattr(pool_item, "pool_item_id") else pool_item.id,
        "platform_id": pool_item.platform_id,
        "platform_key_id": platform_key_id,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "latency_ms": (time.time() - start) * 1000,
        "ttft_ms": ttft,
        "error": error,
        "headers": {
            "X-Fallback-Attempts": str(fallback_count),
            "X-Routed-Via": f"key {platform_key_id} ({pool_item.model})",
        },
    }


def _make_meta_fail(
    platform_id: Optional[int],
    model: Optional[str],
    fallback_count: int,
    start: float,
    error: str,
) -> dict:
    return {
        "pool_item_id": None,
        "platform_id": platform_id,
        "platform_key_id": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": (time.time() - start) * 1000,
        "ttft_ms": 0,
        "error": error,
        "headers": {
            "X-Fallback-Attempts": str(fallback_count),
            "X-Routed-Via": f"{platform_id} ({model})" if platform_id else "",
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
        platform_id=meta.get("platform_id"),
        platform_key_id=meta.get("platform_key_id"),
        provider_id=None,  # 已废弃，使用 platform_key_id
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
    """列出所有 active pool 的名称作为可用 model（OpenAI 格式）"""
    q = select(Pool).where(Pool.is_active == True).order_by(Pool.name)
    pools = (await session.execute(q)).scalars().all()
    return [
        {"id": p.name, "object": "model", "owned_by": "ai-gateway"}
        for p in pools
    ]


class StickySessionManager:
    """Sticky Session 管理器（圆该老接口名称，内部使用 platform_key_id）"""

    @staticmethod
    def make_key(ip: str, first_user_message: str) -> str:
        return ph.StickySessionManager_instance.make_key(ip, first_user_message)

    @staticmethod
    def bind(key: str, platform_key_id: int, model: str):
        ph.StickySessionManager_instance.bind(key, platform_key_id, model)

    @staticmethod
    def resolve(key: str, valid_ids: set):
        """
        解析 sticky session
        Returns:
            (platform_key_id, model) 或 None
        """
        return ph.StickySessionManager_instance.resolve(key, valid_ids)

    @staticmethod
    def count() -> int:
        return ph.StickySessionManager_instance.count()
