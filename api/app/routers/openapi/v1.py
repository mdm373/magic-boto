"""OpenAI-compatible v1 routes: agent loop (tools) and pass-through (models, stream)."""

import json
from collections.abc import AsyncIterator, Iterator

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRouter
from settings import get_settings

from app.agent import run_chat_loop

router = APIRouter(prefix="/v1", tags=["openapi"])


async def _lm_studio_headers_and_body(
    request: Request, method: str
) -> tuple[dict[str, str], bytes | None]:
    """Copy request headers (drop host/content-length) and body for LM Studio."""
    headers = dict(request.headers)
    for key in ("host", "content-length"):
        headers.pop(key, None)
    body = await request.body() if method != "GET" else None
    return headers, body


async def _proxy_to_lm_studio(
    method: str,
    path: str,
    request: Request,
) -> JSONResponse:
    """Forward request to LM Studio and return the JSON response or 502 on error."""
    s = get_settings()
    url = f"{s.lm_studio_base_url}{path}"
    headers, body = await _lm_studio_headers_and_body(request, method)
    params = dict(request.query_params) if request.query_params else None
    async with httpx.AsyncClient(timeout=s.lm_studio_timeout) as client:
        try:
            response = await client.request(
                method, url, content=body, headers=headers, params=params
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "message": f"LM Studio unreachable: {e!s}",
                        "type": "backend_unavailable",
                    },
                },
            )
    try:
        content = response.json() if response.content else {}
    except Exception:
        content = {}
    return JSONResponse(status_code=response.status_code, content=content)


async def _stream_chat_completion_from_lm_studio(
    request: Request,
) -> StreamingResponse | JSONResponse:
    """
    Proxy POST /v1/chat/completions to LM Studio and stream the response body.
    Supports both streaming (SSE) and non-streaming (single JSON) upstream responses.
    """
    s = get_settings()
    url = f"{s.lm_studio_base_url}/v1/chat/completions"
    headers, body = await _lm_studio_headers_and_body(request, "POST")
    params = dict(request.query_params) if request.query_params else None
    client = httpx.AsyncClient(timeout=s.lm_studio_timeout)
    try:
        req = client.build_request("POST", url, content=body, headers=headers, params=params)
        response = await client.send(req, stream=True)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        await client.aclose()
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"LM Studio unreachable: {e!s}",
                    "type": "backend_unavailable",
                },
            },
        )

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
    )


@router.get("/models")
async def list_models(request: Request) -> JSONResponse:
    """
    List available models (OpenAI-compatible). Pass-through to LM Studio.
    """
    return await _proxy_to_lm_studio("GET", "/v1/models", request)


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(request: Request) -> JSONResponse | StreamingResponse:
    """
    Create a chat completion (OpenAI-compatible). Runs agent loop with tools
    (e.g. get_card); returns final message. If stream=true, sends SSE deltas for the UI.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    messages = body.get("messages") or []
    stream_requested = body.get("stream") is True
    if not messages:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "messages is required",
                    "type": "invalid_request_error",
                },
            },
        )
    s = get_settings()
    url = f"{s.lm_studio_base_url.rstrip('/')}/v1/chat/completions"
    model = body.get("model") or ""
    try:
        completion = await run_chat_loop(
            url=url,
            timeout=s.lm_studio_timeout,
            messages=messages,
            model=model,
            temperature=body.get("temperature"),
            max_tokens=body.get("max_tokens"),
        )
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"LM Studio unreachable: {e!s}",
                    "type": "backend_unavailable",
                },
            },
        )
    # Normalize so content is always a string (some backends return null).
    if isinstance(completion, dict):
        choices = completion.get("choices") or []
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message") or {}
            if msg.get("content") is None or not isinstance(msg.get("content"), str):
                msg["content"] = msg.get("content") or ""
                choices[0]["message"] = msg
            if msg.get("role") != "assistant":
                msg["role"] = "assistant"

    if stream_requested:
        # Send SSE in OpenAI delta format so the UI displays the message.
        content = ""
        if isinstance(completion, dict):
            ch = (completion.get("choices") or [None])[0]
            if isinstance(ch, dict):
                m = ch.get("message") or {}
                content = m.get("content") or ""
        cid = "chatcmpl-agent"
        model = ""
        if isinstance(completion, dict):
            cid = completion.get("id", cid)
            model = completion.get("model", "")

        def sse_events() -> Iterator[str]:
            if content:
                chunk = {
                    "id": cid,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            end_chunk = {
                "id": cid,
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(end_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            (e.encode() for e in sse_events()),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    return JSONResponse(content=completion)
