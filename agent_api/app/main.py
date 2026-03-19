"""FastAPI app: OpenAI-compatible routes (models, chat/completions with tool execution)."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .errors import register_app_error_handler
from .routes import create_debug_router, create_open_ai_router, health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load tools/spec at startup, build and mount v1 router. Server not ready until done."""
    app.include_router(await create_open_ai_router(), prefix="/open_ai")
    app.include_router(await create_debug_router(), prefix="/debug")
    app.include_router(health_router, prefix="/health")
    yield


app: FastAPI = FastAPI(
    title="Magic Boto Agent API",
    description="OpenAI-compatible chat; tools from tools_api OpenAPI, executed via HTTP.",
    lifespan=lifespan,
)
register_app_error_handler(app)
