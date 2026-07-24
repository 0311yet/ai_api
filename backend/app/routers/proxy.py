"""代理路由 - OpenAI 兼容接口 + Anthropic /v1/messages

/v1/chat/completions : 代理聊天请求（流式 + 非流式）
/v1/messages         : Anthropic 格式代理（自动转 OpenAI 发给上游）
/v1/models           : 列出可用 pool（作为 model 返回）
"""
import json
import uuid

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, async_session
from app.services import proxy as proxy_svc
from app.services import provider_health as ph

router = APIRouter(prefix="/v1", tags=["proxy"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _first_user_message(body: dict) -> str:
    """从请求体里提取第一条用户消息内容（用于 sticky session key）"""
    if "/v1/messages" in str(body):
        # Anthropic 格式
        for msg in body.get("messages", []):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    return "".join(b.get("text", "") for b in content if b.get("type") == "text")
    elif "/v1/chat/completions" in str(body):
        # OpenAI 格式
        for msg in body.get("messages", []):
            if msg.get("role") == "user":
                return str(msg.get("content", ""))
    return ""


@router.get("/models")
async def get_models(request: Request, session: AsyncSession = Depends(get_session)):
    """列出所有 active 的 pool 作为可用 model（支持 OpenAI / Anthropic 格式协商）"""
    pools = await proxy_svc.list_available_models(session)
    
    # Anthropic 客户端发 anthropic-version header，返回 Anthropic 格式
    is_anthropic = "anthropic-version" in request.headers
    if is_anthropic:
        return {
            "object": "list",
            "data": [
                {"id": "auto", "display_name": "Auto (router picks the best available model)", "created_at": "2026-01-01T00:00:00Z"},
                *pools,
            ],
            "has_more": False,
            "first_id": "auto",
            "last_id": pools[-1]["id"] if pools else None,
        }
    return {"object": "list", "data": pools}


@router.post("/chat/completions")
async def chat_completions(request: Request, session: AsyncSession = Depends(get_session)):
    auth = request.headers.get("authorization", "")
    client_key = await proxy_svc.authenticate_client(session, auth)
    if not client_key:
        raise HTTPException(401, "Invalid client key")

    body = await request.json()
    model = body.get("model")
    if not model:
        raise HTTPException(400, "model is required")
    if not proxy_svc.check_model_allowed(client_key, model):
        raise HTTPException(403, f"Model '{model}' not allowed for this key")

    pool = proxy_svc.resolve_pool_for_key(client_key, model)
    if not pool:
        raise HTTPException(404, f"No active pool matching model '{model}'")

    # Sticky Session：解析
    ip = _client_ip(request)
    first_msg = _first_user_message(body)
    is_stream = body.get("stream", False)
    multi_turn = proxy_svc.is_multi_turn(body.get("messages", []))
    session_key = None
    sticky_platform_key_id = None
    if multi_turn and first_msg:
        session_key = proxy_svc.StickySessionManager.make_key(ip, first_msg)
        valid_ids = {item.platform_key_id for item in pool.pool_items if item.is_active and item.platform_key_id}
        resolved = proxy_svc.StickySessionManager.resolve(session_key, valid_ids)
        if resolved:
            sticky_platform_key_id = resolved[0]

    ua = request.headers.get("user-agent", "")
    request_id = str(uuid.uuid4())
    client_key_id = client_key.id
    extra_headers = {}

    if is_stream:
        code, gen, meta_container = await proxy_svc.proxy_stream_request(pool, body, sticky_platform_key_id)
        if code != 200:
            log = proxy_svc.make_log(client_key_id, model, request_id, "failed", {
                "latency_ms": 0, "ttft_ms": 0, "error": "All upstreams failed",
            }, ip=ip, ua=ua, request_body=json.dumps(body), is_stream=True)
            session.add(log)
            await proxy_svc.increment_key_usage(client_key_id, 0)
            await session.commit()
            return JSONResponse(status_code=502, content={"error": {"message": "All upstreams failed"}})

        async def stream_with_log():
            yield_buffer = []
            total_tokens = 0
            try:
                async for chunk in gen:
                    yield_buffer.append(chunk)
                    yield chunk
            finally:
                meta = meta_container or {}
                total_tokens = meta.get("total_tokens", 0)
                pk_id = meta.get("platform_key_id")
                if pk_id and total_tokens > 0:
                    await ph.record_request(pk_id, model, total_tokens)
                # Sticky Session：成功后绑定
                if session_key and meta.get("platform_key_id"):
                    proxy_svc.StickySessionManager.bind(session_key, meta["platform_key_id"], model)
                async with async_session() as s:
                    log = proxy_svc.make_log(
                        client_key_id, model, request_id, "success", meta,
                        ip=ip, ua=ua,
                        request_body=json.dumps(body),
                        response_body=b"".join(yield_buffer).decode("utf-8", errors="replace")[:5000],
                        is_stream=True,
                    )
                    s.add(log)
                    await s.commit()
                await proxy_svc.increment_key_usage(client_key_id, total_tokens)

        return StreamingResponse(stream_with_log(), media_type="text/event-stream")

    else:
        code, resp_data, meta = await proxy_svc.proxy_json_request(pool, body, sticky_platform_key_id)
        log = proxy_svc.make_log(
            client_key_id, model, request_id,
            "success" if code == 200 else "failed",
            meta, ip=ip, ua=ua,
            request_body=json.dumps(body),
            response_body=json.dumps(resp_data)[:5000] if code == 200 else "",
            is_stream=False,
        )
        session.add(log)
        await session.commit()
        await proxy_svc.increment_key_usage(client_key_id, meta.get("total_tokens", 0))
        # Sticky Session：成功后绑定
        if code == 200 and session_key and meta.get("platform_key_id"):
            proxy_svc.StickySessionManager.bind(session_key, meta["platform_key_id"], model)
        # 注入响应头
        extra_headers = meta.get("headers", {})
        if code == 200:
            return JSONResponse(content=resp_data, headers=extra_headers)
        return JSONResponse(status_code=code, content=resp_data, headers=extra_headers)


# ---------- Anthropic /v1/messages 支持 ----------

def _anthropic_to_openai(body: dict) -> dict:
    """Anthropic /v1/messages 格式 → OpenAI /v1/chat/completions 格式"""
    messages = body.get("messages", [])
    openai_messages = []
    for msg in messages:
        role = msg.get("role")
        content_raw = msg.get("content", "")
        if isinstance(content_raw, list):
            text = "".join(b.get("text", "") for b in content_raw if b.get("type") == "text")
        else:
            text = content_raw
        if role == "assistant":
            openai_messages.append({"role": "assistant", "content": text})
        elif role == "user":
            openai_messages.append({"role": "user", "content": text})
        elif role == "system":
            openai_messages.append({"role": "system", "content": text})
    return {
        "model": body.get("model", "auto"),
        "messages": openai_messages,
        "max_tokens": body.get("max_tokens", 1024),
        "stream": body.get("stream", False),
    }


def _finish_reason_to_stop_reason(reason: str) -> str:
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "content_filter",
        "tool_calls": "end_turn",
    }
    return mapping.get(reason, "end_turn")


def _openai_to_anthropic(resp_data: dict, model: str, request_id: str) -> dict:
    """OpenAI chat completion → Anthropic message 格式"""
    choice = (resp_data.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    content_raw = msg.get("content", "")
    if isinstance(content_raw, str):
        anthropic_content = [{"type": "text", "text": content_raw}]
    else:
        anthropic_content = content_raw
    usage = resp_data.get("usage", {})
    return {
        "id": f"msg_{request_id[:8]}",
        "type": "message",
        "role": "assistant",
        "content": anthropic_content,
        "model": model,
        "stop_reason": _finish_reason_to_stop_reason(choice.get("finish_reason", "stop")),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
        "created": resp_data.get("created", 0),
    }


def _stream_openai_to_anthropic(raw_bytes: bytes, model: str) -> bytes:
    """OpenAI SSE 流 → Anthropic event stream"""
    text = raw_bytes.decode("utf-8", errors="replace")
    out_lines = []
    for line in text.split("\n"):
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            out_lines.append("event: message_stop\ndata: {}")
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        choice = (obj.get("choices") or [{}])[0]
        delta = choice.get("delta", {})
        finish = choice.get("finish_reason")
        if delta.get("role"):
            out_lines.append(
                'event: content_block_start\n'
                'data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}}'
            )
        if delta.get("content"):
            safe = json.dumps(delta["content"])
            out_lines.append(
                f"event: content_block_delta\n"
                f"data: {{\"type\": \"content_block_delta\", \"index\": 0, \"delta\": {{\"type\": \"text_delta\", \"text\": {safe}}}}}"
            )
        if finish:
            out_lines.append(
                f"event: message_delta\n"
                f"data: {{\"type\": \"message_delta\", \"index\": 0, \"delta\": {{\"stop_reason\": {json.dumps(_finish_reason_to_stop_reason(finish))}}}}}"
            )
            out_lines.append("event: message_stop\ndata: {}")
    return ("\n".join(out_lines) + "\n").encode("utf-8")


@router.post("/messages")
async def anthropic_messages(request: Request, session: AsyncSession = Depends(get_session)):
    """Anthropic /v1/messages 端点：转换为 OpenAI 格式代理给上游"""
    auth = request.headers.get("authorization", "")
    client_key = await proxy_svc.authenticate_client(session, auth)
    if not client_key:
        raise HTTPException(401, "Invalid client key")

    body = await request.json()
    model = body.get("model")
    if not model:
        raise HTTPException(400, "model is required")
    if not proxy_svc.check_model_allowed(client_key, model):
        raise HTTPException(403, f"Model '{model}' not allowed for this key")

    pool = proxy_svc.resolve_pool_for_key(client_key, model)
    if not pool:
        raise HTTPException(404, f"No active pool matching model '{model}'")

    # Sticky Session：解析
    ip = _client_ip(request)
    first_msg = _first_user_message(body)
    is_stream = body.get("stream", False)
    multi_turn = proxy_svc.is_multi_turn(body.get("messages", []))
    session_key = None
    sticky_provider_id = None
    if multi_turn and first_msg:
        session_key = proxy_svc.StickySessionManager.make_key(ip, first_msg)
        valid_ids = {item.platform_key_id for item in pool.pool_items if item.is_active and item.platform_key_id}
        resolved = proxy_svc.StickySessionManager.resolve(session_key, valid_ids)
        if resolved:
            sticky_provider_id = resolved[0]

    ua = request.headers.get("user-agent", "")
    request_id = str(uuid.uuid4())
    client_key_id = client_key.id
    raw_request_body = json.dumps(body)
    openai_body = _anthropic_to_openai(body)
    extra_headers = {}

    if is_stream:
        code, gen, meta_container = await proxy_svc.proxy_stream_request(pool, openai_body, sticky_provider_id)
        if code != 200:
            log = proxy_svc.make_log(client_key_id, model, request_id, "failed", {
                "latency_ms": 0, "ttft_ms": 0, "error": "All upstreams failed",
            }, ip=ip, ua=ua, request_body=raw_request_body, is_stream=True)
            session.add(log)
            await proxy_svc.increment_key_usage(client_key_id, 0)
            await session.commit()
            return JSONResponse(
                status_code=502,
                content={
                    "type": "error",
                    "error": {"type": "invalid_request_error", "message": "All upstreams failed"},
                },
            )

        async def stream_with_log():
            yield_buffer = []
            total_tokens = 0
            try:
                async for chunk in gen:
                    converted = _stream_openai_to_anthropic(chunk, model)
                    yield_buffer.append(converted)
                    yield converted
            finally:
                meta = meta_container or {}
                total_tokens = meta.get("total_tokens", 0)
                pk_id = meta.get("platform_key_id")
                if pk_id and total_tokens > 0:
                    await ph.record_request(pk_id, model, total_tokens)
                if session_key and meta.get("platform_key_id"):
                    proxy_svc.StickySessionManager.bind(session_key, meta["platform_key_id"], model)
                async with async_session() as s:
                    combined = b"".join(yield_buffer).decode("utf-8", errors="replace")[:5000]
                    log = proxy_svc.make_log(
                        client_key_id, model, request_id, "success", meta,
                        ip=ip, ua=ua, request_body=raw_request_body,
                        response_body=combined, is_stream=True,
                    )
                    s.add(log)
                    await s.commit()
                await proxy_svc.increment_key_usage(client_key_id, total_tokens)

        return StreamingResponse(
            stream_with_log(),
            media_type="text/event-stream",
            headers={"x-request-id": request_id},
        )
    else:
        code, resp_data, meta = await proxy_svc.proxy_json_request(pool, openai_body, sticky_provider_id)
        anthropic_resp = _openai_to_anthropic(resp_data, model, request_id)
        log = proxy_svc.make_log(
            client_key_id, model, request_id,
            "success" if code == 200 else "failed",
            meta, ip=ip, ua=ua,
            request_body=raw_request_body,
            response_body=json.dumps(anthropic_resp)[:5000] if code == 200 else "",
            is_stream=False,
        )
        session.add(log)
        await session.commit()
        await proxy_svc.increment_key_usage(client_key_id, meta.get("total_tokens", 0))
        if code == 200 and session_key and meta.get("platform_key_id"):
            proxy_svc.StickySessionManager.bind(session_key, meta["platform_key_id"], model)
        extra_headers = meta.get("headers", {})
        if code == 200:
            return JSONResponse(content=anthropic_resp, headers=extra_headers)
        err_msg = resp_data.get("error", {}).get("message", "Proxy error")
        return JSONResponse(
            status_code=code,
            content={
                "type": "error",
                "error": {"type": "invalid_request_error", "message": err_msg},
            },
            headers=extra_headers,
        )
