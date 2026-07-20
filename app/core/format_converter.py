"""
Format converter - OpenAI <-> Claude

Handles:
- Request format conversion
- Response format conversion
- Token estimation
- Stream response parsing
"""
import json
import re
import time
from typing import Optional, Tuple, Dict


def build_upstream_request(
    channel: "Channel", api_key: str, body: dict
) -> Tuple[str, dict, dict, str]:
    """
    Build upstream request

    Returns: (url, headers, payload, response_format)
    response_format: "openai" | "anthropic"
    """
    provider = channel.provider.lower()
    url = channel.base_url.rstrip("/")

    # Path handling
    if provider == "anthropic":
        path = "/v1/messages"
    elif provider == "google":
        path = "/v1beta/models/{model}:generateContent"
    else:  # openai or local
        path = "/v1/chat/completions"

    url = f"{url}{path}"

    # Build headers
    headers = {
        "Content-Type": "application/json",
    }

    # Add API key
    if provider == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    # Convert request body
    payload = {}
    response_format = "openai"

    if provider == "anthropic":
        # OpenAI -> Anthropic
        response_format = "anthropic"
        messages = []

        system_msg = None
        user_msgs = []

        for msg in body.get("messages", []):
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                user_msgs.append(msg)

        payload = {
            "model": body.get("model"),
            "max_tokens": body.get("max_tokens", 1024),
            "messages": [
                {"role": "user" if system_msg else "assistant" if msg["role"] == "assistant" else "user", "content": content}
                for msg in user_msgs
            ],
            "stream": body.get("stream", False),
        }

        if system_msg:
            payload["system"] = system_msg

        # Additional params
        if "temperature" in body:
            payload["temperature"] = body["temperature"]
        if "top_p" in body:
            payload["top_p"] = body["top_p"]
        if "stop_sequences" in body:
            payload["stop_sequences"] = body["stop_sequences"]

    elif provider == "google":
        # OpenAI -> Google
        messages = []
        for msg in body.get("messages", []):
            if msg["role"] == "system":
                # Google uses first message as systemInstruction
                if len(messages) == 0:
                    messages.append({
                        "role": "user",
                        "parts": [{"text": msg["content"]}]
                    })
                continue
            role = msg["role"]
            if role == "assistant":
                role = "model"
            messages.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        payload = {
            "contents": messages,
            "generationConfig": {
                "maxOutputTokens": body.get("max_tokens", 1024),
            },
            "temperature": body.get("temperature", 0.7),
            "topP": body.get("top_p", 1.0),
        }

        if "stop" in body:
            payload["generationConfig"]["stopSequences"] = body["stop"]

    else:  # openai/local
        payload = body
        response_format = "openai"

    return url, headers, payload, response_format


def parse_upstream_response(
    result: dict, response_format: str, original_body: dict
) -> dict:
    """
    Parse upstream response and convert format

    Returns: converted OpenAI format
    """
    if response_format == "openai":
        # OpenAI format, return directly
        return result

    elif response_format == "anthropic":
        # Anthropic -> OpenAI
        content = result.get("content", [])
        messages = []

        # Build full conversation history
        for msg in content:
            role = "assistant" if msg.get("role") == "assistant" else "user"
            messages.append({
                "role": role,
                "content": msg["text"]
            })

        # Merge original messages (keep subsequent dialogue)
        if len(original_body.get("messages", [])) > len(messages):
            messages.extend(original_body["messages"][len(messages):])

        # Extract usage
        usage = result.get("usage", {})
        total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        return {
            "id": result.get("id", f"chatcmpl-{hash(str(result))}"),
            "object": "chat.completion",
            "created": int(result.get("created", time.time())),
            "model": result.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content[0]["text"] if content else "",
                    },
                    "finish_reason": result.get("stop_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        }

    elif response_format == "google":
        # Google -> OpenAI
        contents = result.get("candidates", [])
        if not contents:
            return {}

        choice = contents[0]
        content_parts = choice.get("content", {}).get("parts", [])
        text = "\n".join(p.get("text", "") for p in content_parts)

        usage = result.get("usageMetadata", {})
        total_tokens = usage.get("totalTokenCount", 0)
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        return {
            "id": f"chatcmpl-{hash(str(result))}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": result.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        }

    return result


def count_text_tokens(text: str) -> int:
    """
    Estimate tokens for text:
    - Chinese: ~1.5 tokens per character
    - English: ~0.25 tokens per character
    """
    tokens = 0
    for c in text:
        if ord(c) > 127:
            tokens += 1.5
        else:
            tokens += 0.25
    return int(tokens)


def parse_upstream_stream_chunk(
    line: str, response_format: str, original_body: dict
) -> Tuple[Optional[str], Optional[str], Optional[dict], int]:
    """
    Parse stream response chunk

    Returns: (converted_line, finish_reason, usage_update, output_chars)
    """
    if not line.startswith("data:"):
        return None, None, None, 0

    data_str = line[5:].strip()
    if data_str == "[DONE]":
        return None, "[DONE]", None, 0

    try:
        data = json.loads(data_str)
    except:
        return None, None, None, 0

    output_chars = 0

    if response_format == "openai":
        # OpenAI -> OpenAI (forward directly)
        if "choices" in data:
            choice = data["choices"][0]
            if "delta" in choice:
                delta = choice["delta"]
                output_chars += len(delta.get("content", ""))
                return f"data: {json.dumps(data)}\n\n", None, None, output_chars

        # Handle usage
        usage = data.get("usage", {})
        if usage:
            return None, None, usage, output_chars

    elif response_format == "anthropic":
        # Anthropic -> OpenAI (convert format)
        if data.get("type") == "message_start":
            # Send empty message placeholder
            return f"data: {json.dumps({'id': 'connected', 'object': 'chat', 'created': int(time.time())})}\n\n", None, None, 0

        if data.get("type") == "content_block_delta":
            block = data.get("delta", {})
            content = block.get("text", "")
            output_chars += len(content)

            # Convert to OpenAI format
            chunk = {
                "id": f"chatcmpl-{hash(str(data))}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": data.get("message", {}).get("model"),
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": content},
                        "finish_reason": None,
                    }
                ]
            }
            return f"data: {json.dumps(chunk)}\n\n", None, None, output_chars

        if data.get("type") == "message_delta":
            usage = data.get("delta", {}).get("stop_reason")
            finish_reason = usage
            if usage == "max_tokens":
                finish_reason = "length"
            return None, finish_reason, None, output_chars

        if data.get("type") == "message_stop":
            return None, "stop", None, output_chars

    elif response_format == "google":
        # Google -> OpenAI (simple conversion)
        if "candidates" in data:
            candidate = data["candidates"][0]
            content = candidate.get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in content)
            output_chars += len(text)

            # Convert to OpenAI format
            chunk = {
                "id": f"chatcmpl-{hash(str(data))}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": data.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": text},
                        "finish_reason": None,
                    }
                ]
            }
            return f"data: {json.dumps(chunk)}\n\n", None, None, output_chars

        if data.get("usageMetadata"):
            usage = data["usageMetadata"]
            return None, None, {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            }, output_chars

    return None, None, None, output_chars


def extract_usage_from_stream(line: str) -> Optional[dict]:
    """Extract usage from stream response"""
    if not line.startswith("data:"):
        return None

    data_str = line[5:].strip()
    if data_str == "[DONE]":
        return None

    try:
        data = json.loads(data_str)
    except:
        return None

    if "usage" in data:
        return data["usage"]

    if "usage" in data.get("choices", [{}])[0]:
        return data["choices"][0]["usage"]

    return None


def estimate_tokens(body: dict, output_chars: int = 0) -> dict:
    """
    Simple token estimation

    1 Chinese char = 1.5 tokens
    1 English char = 0.25 tokens
    """
    total_chars = output_chars

    # Count chars in prompt
    prompt_tokens = 0
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        total_chars += len(content)

    # Count tokens in prompt
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        prompt_tokens += count_text_tokens(content)

    # Count tokens in completion
    completion_tokens = 0
    # Use first message's content for the completion estimate
    if body.get("messages") and len(body["messages"]) > 0:
        last_msg = body["messages"][-1]
        if last_msg.get("role") == "assistant":
            completion_tokens = count_text_tokens(last_msg.get("content", ""))

    return {
        "prompt": prompt_tokens,
        "completion": completion_tokens,
        "total": prompt_tokens + completion_tokens
    }