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
from app.services.proxy import (
    authenticate_client, check_model_allowed, resolve_pool_for_key,
    proxy_json_request, proxy_stream_request,
    make_log, increment_key_usage, list_available_models,
)

router = APIRouter(prefix="/v1", tags=["proxy"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.get("/models")
async def get_models(session: AsyncSession = Depends(get_session)):
    """列出所有 active 的 pool 作为可用 model"""
    return {"object": "list", "data": await list_available_models(session)}


@router.post("/chat/completions")
async def chat_completions(request: Request, session: AsyncSession = Depends(get_session)):
    auth = request.headers.get("authorization", "")
    client_key = await authenticate_client(session, auth)
    if not client_key:
        raise HTTPException(401, "Invalid client key")

    body = await request.json()
    model = body.get("model")
    if not model:
        raise HTTPException(400, "model is required")
    if not check_model_allowed(client_key, model):
        raise HTTPException(403, f"Model '{model}' not allowed for this key")

    pool = resolve_pool_for_key(client_key, model)
    if not pool:
        raise HTTPException(404, f"No active pool matching model '{model}'")

    is_stream = body.get("stream", False)
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    request_id = str(uuid.uuid4())
    client_key_id = client_key.id

    if is_stream:
        code, gen, meta_container = await proxy_stream_request(pool, body)
        if code != 200:
            log = make_log(client_key_id, model, request_id, "failed", {
                "latency_ms": 0, "ttft_ms": 0, "error": "All upstreams failed",
            }, ip=ip, ua=ua, request_body=json.dumps(body), is_stream=True)
            session.add(log)
            await increment_key_usage(client_key_id, 0)
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
                async with async_session() as s:
                    log = make_log(
                        client_key_id, model, request_id, "success", meta,
                        ip=ip, ua=ua,
                        request_body=json.dumps(body),
                        response_body=b"".join(yield_buffer).decode("utf-8", errors="replace")[:5000],
                        is_stream=True,
                    )
                    s.add(log)
                    await s.commit()
                await increment_key_usage(client_key_id, total_tokens)

        return StreamingResponse(stream_with_log(), media_type="text/event-stream")

    else:
        code, resp_data, meta = await proxy_json_request(pool, body)
        log = make_log(
            client_key_id, model, request_id,
            "success" if code == 200 else "failed",
            meta,
            ip=ip, ua=ua,
            request_body=json.dumps(body),
            response_body=json.dumps(resp_data)[:5000] if code == 200 else "",
            is_stream=False,
        )
        session.add(log)
        await session.commit()
        await increment_key_usage(client_key_id, meta.get("total_tokens", 0))
        if code == 200:
            return JSONResponse(content=resp_data)
        return JSONResponse(status_code=code, content=resp_data)


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
    client_key = await authenticate_client(session, auth)
    if not client_key:
        raise HTTPException(401, "Invalid client key")

    body = await request.json()
    model = body.get("model")
    if not model:
        raise HTTPException(400, "model is required")
    if not check_model_allowed(client_key, model):
        raise HTTPException(403, f"Model '{model}' not allowed for this key")

    pool = resolve_pool_for_key(client_key, model)
    if not pool:
        raise HTTPException(404, f"No active pool matching model '{model}'")

    is_stream = body.get("stream", False)
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    request_id = str(uuid.uuid4())
    client_key_id = client_key.id
    raw_request_body = json.dumps(body)
    openai_body = _anthropic_to_openai(body)

    if is_stream:
        code, gen, meta_container = await proxy_stream_request(pool, openai_body)
        if code != 200:
            log = make_log(client_key_id, model, request_id, "failed", {
                "latency_ms": 0, "ttft_ms": 0, "error": "All upstreams failed",
            }, ip=ip, ua=ua, request_body=raw_request_body, is_stream=True)
            session.add(log)
            await increment_key_usage(client_key_id, 0)
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
                async with async_session() as s:
                    combined = b"".join(yield_buffer).decode("utf-8", errors="replace")[:5000]
                    log = make_log(
                        client_key_id, model, request_id, "success", meta,
                        ip=ip, ua=ua, request_body=raw_request_body,
                        response_body=combined, is_stream=True,
                    )
                    s.add(log)
                    await s.commit()
                await increment_key_usage(client_key_id, total_tokens)

        return StreamingResponse(
            stream_with_log(),
            media_type="text/event-stream",
            headers={"x-request-id": request_id},
        )
    else:
        code, resp_data, meta = await proxy_json_request(pool, openai_body)
        anthropic_resp = _openai_to_anthropic(resp_data, model, request_id)
        log = make_log(
            client_key_id, model, request_id,
            "success" if code == 200 else "failed",
            meta, ip=ip, ua=ua,
            request_body=raw_request_body,
            response_body=json.dumps(anthropic_resp)[:5000] if code == 200 else "",
            is_stream=False,
        )
        session.add(log)
        await session.commit()
        await increment_key_usage(client_key_id, meta.get("total_tokens", 0))
        if code == 200:
            return JSONResponse(content=anthropic_resp)
        err_msg = resp_data.get("error", {}).get("message", "Proxy error")
        return JSONResponse(
            status_code=code,
            content={
                "type": "error",
                "error": {"type": "invalid_request_error", "message": err_msg},
            },
        )