"""代理服务 - 转发客户端请求到上游 Provider

核心流程：
1. 验证 client key → 找到绑定的 Pool
2. PoolRouter 选 PoolItem → 找到 Provider
3. 转发请求到 Provider.base_url/chat/completions
4. 失败回退到下一个 PoolItem
5. 记录 RequestLog（含 token 统计、延迟、TTFT）
"""
import time
import json
import uuid
from datetime import datetime
from typing import Optional, AsyncGenerator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.config import settings
from app.models import ClientKey, Pool, PoolItem, Provider, RequestLog
from app.services.pool_router import PoolRouter


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
        return True  # 空数组 = 不限制
    return model in client_key.allowed_models


def resolve_pool_for_key(client_key: ClientKey, model: str) -> Optional[Pool]:
    """从 client_key 绑定的 pool 找到（用客户端传入的 model 名匹配 Pool.name）"""
    pool = client_key.pool
    if not pool or not pool.is_active:
        return None
    if pool.name != model:
        return None  # 客户端请求的 model 必须等于 pool.name（一对一绑定模型）
    return pool


async def get_ordered_items(pool: Pool) -> list:
    """根据 pool.strategy 给出按策略排序的候选 PoolItem 列表（用于失败回退）"""
    router = PoolRouter(pool.pool_items)
    return router.select_all_ordered(pool.strategy)


async def proxy_json_request(
    pool: Pool,
    body: dict,
) -> tuple:
    """非流式代理

    返回 (code, resp_dict, log_dict)
    log_dict: 用于 make_log 构造 RequestLog 的 {pool_item_id, provider_id, prompt_tokens, completion_tokens, total_tokens, latency_ms, ttft_ms, error}
    """
    start = time.time()
    ordered = (await get_ordered_items(pool))

    last_error = ""
    for item in ordered:
        if not item.provider or not item.provider.is_active:
            continue
        upstream_url = f"{item.provider.base_url.rstrip('/')}/chat/completions"
        upstream_body = {**body, "model": item.model, "stream": False}
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
                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {}) or {}
                    pt = usage.get("prompt_tokens", 0)
                    ct = usage.get("completion_tokens", 0)
                    return (
                        200,
                        data,
                        {
                            "pool_item_id": item.id,
                            "provider_id": item.provider.id,
                            "prompt_tokens": pt,
                            "completion_tokens": ct,
                            "total_tokens": pt + ct,
                            "latency_ms": (time.time() - start) * 1000,
                            "ttft_ms": ttft,
                            "error": "",
                        },
                    )
                else:
                    last_error = f"Upstream {resp.status_code}"
                    continue
        except httpx.TimeoutException:
            last_error = f"Timeout from {item.provider.name}"
        except Exception as e:
            last_error = f"{item.provider.name} error: {str(e)}"
    return 502, {"error": {"message": f"All upstreams failed: {last_error}"}}, {
        "pool_item_id": None,
        "provider_id": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": (time.time() - start) * 1000,
        "ttft_ms": 0,
        "error": last_error,
    }


async def proxy_stream_request(
    pool: Pool,
    body: dict,
) -> tuple:
    """流式代理 - 边收边吐

    返回 (code, async_gen, log_callback)：
    - code == 200: async_gen 是 yield 原汁原味 SSE bytes 的 generator
    - log_callback: async 函数，在流完后调用，返回日志 dict
    """
    start = time.time()
    ordered = await get_ordered_items(pool)

    for item in ordered:
        if not item.provider or not item.provider.is_active:
            continue
        upstream_url = f"{item.provider.base_url.rstrip('/')}/chat/completions"
        upstream_body = {**body, "model": item.model, "stream": True}

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
            if resp.status_code == 200:
                chosen_item_id = item.id
                chosen_provider_id = item.provider.id
                meta_container = {}  # gen finally 块写入这里，stream_with_log 读
                meta_container_ref = meta_container


                async def gen():
                    total_tokens = 0
                    yield_counter = 0
                    gen_pt = [0]  # 最后从 usage 里解析的 pt
                    gen_ct = [0]  # 同上 ct
                    try:
                        async for chunk in resp.aiter_bytes():
                            yield_counter += 1
                            # 尝试从 SSE 行里提 usage
                            for line in chunk.decode("utf-8", errors="replace").split("\n"):
                                if line.startswith("data: "):
                                    payload = line[6:].strip()
                                    if payload and payload != "[DONE]":
                                        try:
                                            obj = json.loads(payload)
                                            u = obj.get("usage", {}) or {}
                                            if u:
                                                total_tokens = u.get("total_tokens", total_tokens)
                                                pt_val = u.get("prompt_tokens", 0) or 0
                                                ct_val = u.get("completion_tokens", 0) or 0
                                                # 保存最后一次含 usage 的解析值
                                                gen_pt[0] = pt_val
                                                gen_ct[0] = ct_val
                                        except json.JSONDecodeError:
                                            pass
                            yield chunk
                    finally:
                        await resp.aclose()
                        await client.aclose()
                        meta_container_ref.update({
                            "total_tokens": total_tokens,
                            "prompt_tokens": gen_pt[0],
                            "completion_tokens": gen_ct[0],
                            "latency_ms": (time.time() - start) * 1000,
                            "ttft_ms": ttft,
                            "pool_item_id": chosen_item_id,
                            "provider_id": chosen_provider_id,
                            "error": "",
                        })

                return 200, gen(), meta_container
            else:
                await resp.aread()
                await resp.aclose()
                await client.aclose()
                last_error = f"Upstream {resp.status_code}"
                continue
        except httpx.TimeoutException:
            last_error = f"Timeout from {item.provider.name}"
        except Exception as e:
            last_error = f"{item.provider.name} error: {str(e)}"
    return 502, None, None


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
