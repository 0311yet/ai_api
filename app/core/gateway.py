"""
网关核心 - 处理OpenAI格式请求转发

支持：
- 转发到不同后端(openai/anthropic/google)
- 流式SSE响应
- TTFT(首token)测量
- 格式转换: OpenAI <-> Anthropic
"""
import asyncio
import time
import uuid
import json
from typing import AsyncGenerator, Optional
from datetime import datetime
from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Key, RequestLog
from app.core.pool import KeyPool
from app.core.router import find_channels_for_model
from app.core.format_converter import (
    build_upstream_request,
    parse_upstream_response,
    parse_upstream_stream_chunk,
    estimate_tokens,
    extract_usage_from_stream,
)
from app.config import REQUEST_TIMEOUT


class Gateway:
    """AI网关"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.key_pool = KeyPool(session)
    
    async def handle_chat_completion(self, request: Request) -> StreamingResponse | JSONResponse:
        """处理 /v1/chat/completions 请求"""
        start_time = time.time()
        body = await request.json()
        model_name = body.get("model", "")
        is_stream = body.get("stream", False)
        request_id = str(uuid.uuid4())
        client_ip = request.client.host if request.client else ""
        user_agent = request.headers.get("user-agent", "")
        
        # 查找匹配通道
        channels = await find_channels_for_model(self.session, model_name)
        if not channels:
            return JSONResponse(
                status_code=404,
                content={"error": {"message": f"No channel configured for model: {model_name}", "type": "invalid_request_error"}}
            )
        
        # 创建日志记录
        request_log = RequestLog(
            model=model_name,
            request_id=request_id,
            ip_address=client_ip,
            user_agent=user_agent,
            request_body=json.dumps(body, ensure_ascii=False)[:5000],
            status="pending",
        )
        self.session.add(request_log)
        await self.session.commit()
        
        # 尝试每个通道（故障转移）
        last_error = None
        for channel in channels:
            # 获取密钥
            key = await self.key_pool.get_available_key(channel.id)
            if not key:
                last_error = f"No available key in channel: {channel.name}"
                continue
            
            request_log.channel_id = channel.id
            request_log.key_id = key.id
            await self.session.commit()
            
            try:
                if is_stream:
                    return await self._handle_stream(
                        channel, key, body, request_log, start_time
                    )
                else:
                    return await self._handle_non_stream(
                        channel, key, body, request_log, start_time
                    )
            except Exception as e:
                last_error = str(e)
                await self.key_pool.report_error(key.id, f"{type(e).__name__}: {e}")
                # 继续尝试下一个通道
                continue
        
        # 所有通道失败
        request_log.status = "failed"
        request_log.error_message = last_error or "All channels failed"
        request_log.latency_ms = (time.time() - start_time) * 1000
        await self.session.commit()
        
        return JSONResponse(
            status_code=502,
            content={"error": {"message": last_error or "All channels failed", "type": "upstream_error"}}
        )
    
    async def _handle_non_stream(
        self, channel: Channel, key: Key, body: dict, request_log: RequestLog, start_time: float
    ) -> JSONResponse:
        """非流式响应"""
        upstream_url, headers, payload, response_format = build_upstream_request(
            channel, key.key_value, body
        )
        
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(upstream_url, headers=headers, json=payload)
        
        latency_ms = (time.time() - start_time) * 1000
        
        if resp.status_code != 200:
            request_log.status = "failed"
            request_log.error_message = resp.text[:500]
            request_log.error_code = str(resp.status_code)
            request_log.latency_ms = latency_ms
            await self.session.commit()
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        
        # 解析响应
        result = parse_upstream_response(resp.json(), response_format, body)
        usage = result.get("usage", {})
        
        request_log.status = "success"
        request_log.prompt_tokens = usage.get("prompt_tokens", 0)
        request_log.completion_tokens = usage.get("completion_tokens", 0)
        request_log.total_tokens = usage.get("total_tokens", 0)
        request_log.latency_ms = latency_ms
        request_log.ttft_ms = latency_ms  # 非流式，TTFT等于总延迟
        await self.session.commit()
        
        return JSONResponse(content=result)
    
    async def _handle_stream(
        self, channel: Channel, key: Key, body: dict, request_log: RequestLog, start_time: float
    ) -> StreamingResponse:
        """流式响应"""
        upstream_url, headers, payload, response_format = build_upstream_request(
            channel, key.key_value, body
        )
        
        async def stream_generator() -> AsyncGenerator[bytes, None]:
            ttft_recorded = False
            total_output_chars = 0
            finish_reason = None
            accumulated_usage = {}
            
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    async with client.stream("POST", upstream_url, headers=headers, json=payload) as resp:
                        if resp.status_code != 200:
                            error_text = ""
                            async for chunk in resp.aiter_text():
                                error_text += chunk
                            request_log.status = "failed"
                            request_log.error_message = error_text[:500]
                            request_log.error_code = str(resp.status_code)
                            request_log.latency_ms = (time.time() - start_time) * 1000
                            await self.session.commit()
                            yield f"data: {json.dumps({'error': {'message': error_text[:500], 'type': 'upstream_error'}})}\n\n".encode()
                            yield b"data: [DONE]\n\n"
                            return
                        
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            
                            # 记录首个token时间
                            if not ttft_recorded and line.startswith("data:") and line.strip() != "data: [DONE]":
                                request_log.ttft_ms = (time.time() - start_time) * 1000
                                request_log.first_token_at = time.time()
                                ttft_recorded = True
                            
                            # 转换格式
                            converted, finish, usage_update, output_chars = parse_upstream_stream_chunk(
                                line, response_format, body
                            )
                            if finish:
                                finish_reason = finish
                            if usage_update:
                                accumulated_usage.update(usage_update)
                            total_output_chars += output_chars
                            
                            if converted:
                                yield converted
                
                # 流结束，更新日志
                request_log.status = "success"
                request_log.latency_ms = (time.time() - start_time) * 1000
                
                # 估算token（如果上游没有返回usage）
                if accumulated_usage:
                    request_log.prompt_tokens = accumulated_usage.get("prompt_tokens", 0)
                    request_log.completion_tokens = accumulated_usage.get("completion_tokens", 0)
                    request_log.total_tokens = accumulated_usage.get("total_tokens", 
                                                                      request_log.prompt_tokens + request_log.completion_tokens)
                else:
                    est = estimate_tokens(body, total_output_chars)
                    request_log.prompt_tokens = est["prompt"]
                    request_log.completion_tokens = est["completion"]
                    request_log.total_tokens = est["total"]
                
                await self.session.commit()
                
            except Exception as e:
                request_log.status = "failed"
                request_log.error_message = str(e)[:500]
                request_log.latency_ms = (time.time() - start_time) * 1000
                await self.session.commit()
                yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'gateway_error'}})}\n\n".encode()
                yield b"data: [DONE]\n\n"
        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")