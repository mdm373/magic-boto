"""OpenAI-compatible v1 routes: models pass-through and chat completions with tool execution."""

import json
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from loguru import logger
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    Choice,
    ChoiceDelta,
)
from openai.types.chat.completion_create_params import CompletionCreateParams
from pydantic import TypeAdapter
from sse_starlette import EventSourceResponse, ServerSentEvent

from .errors import invalid_request_error
from .services import Agent, HttpProxy

OBJECT_CHAT_COMPLETION_CHUNK: Literal["chat.completion.chunk"] = "chat.completion.chunk"

_COMPLETION_BODY_ADAPTER: TypeAdapter[CompletionCreateParams] = TypeAdapter(CompletionCreateParams)

health_router = APIRouter(tags=["health"])


def create_openapi_v1_router(
    agent: Agent,
    openai_proxy: HttpProxy,
) -> APIRouter:
    """
    Build the OpenAPI v1 router with tools and spec injected. Call once at startup
    after loading resources; server is not ready until then.
    """
    router = APIRouter(prefix="/v1", tags=["openapi"])

    @router.get("/models")
    async def list_models(request: Request) -> JSONResponse:
        """List available models (OpenAI-compatible). Pass-through to LM Studio."""
        return await openai_proxy.proxy_request("GET", "/v1/models", request)

    @router.post("/chat/completions", response_model=None)
    async def create_chat_completion(
        body: CompletionCreateParams = Depends(_parse_completion_body),
    ) -> ChatCompletion | EventSourceResponse:
        completion = await agent.run_chat_loop(body)
        if body.get("stream") is True:
            return _completion_to_sse_response(completion)
        return completion

    return router


@health_router.get("/")
def health() -> dict[str, str]:
    """Healthcheck."""
    return {"status": "ok"}


async def _parse_completion_body(request: Request) -> CompletionCreateParams:
    """Parse and validate request body as SDK CompletionCreateParams."""
    raw = await request.json()
    if not isinstance(raw, dict):
        raise invalid_request_error("Request body must be a JSON object")
    body = _COMPLETION_BODY_ADAPTER.validate_python(raw)
    if not body.get("messages"):
        raise invalid_request_error("messages is required")
    return body


def _completion_to_sse_response(completion: ChatCompletion) -> EventSourceResponse:
    """Turn a non-streaming ChatCompletion into an SSE response."""
    first = completion.choices[0] if completion.choices else None
    content = first.message.content if first and first.message.content else ""

    async def sse_events() -> AsyncIterator[ServerSentEvent]:
        if content:
            chunk = ChatCompletionChunk(
                id=completion.id,
                created=completion.created,
                model=completion.model,
                object=OBJECT_CHAT_COMPLETION_CHUNK,
                choices=[
                    Choice(
                        delta=ChoiceDelta(content=content),
                        finish_reason=None,
                        index=0,
                    )
                ],
            )
            yield ServerSentEvent(data=chunk.model_dump_json())
        end_chunk = ChatCompletionChunk(
            id=completion.id,
            created=completion.created,
            model=completion.model,
            object=OBJECT_CHAT_COMPLETION_CHUNK,
            choices=[Choice(delta=ChoiceDelta(), finish_reason="stop", index=0)],
        )
        yield ServerSentEvent(data=end_chunk.model_dump_json())
        yield ServerSentEvent(data="[DONE]")

    return EventSourceResponse(
        sse_events(),
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
