"""FastAPI app: OpenAI-compatible routes (models, chat/completions with tool execution)."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .errors import register_app_error_handler
from .router import create_openapi_v1_router, health_router
from .services import create_agent, create_openai_proxy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load tools/spec at startup, build and mount v1 router. Server not ready until done."""
    agent = await create_agent()
    openai_proxy = create_openai_proxy()
    app.include_router(create_openapi_v1_router(agent, openai_proxy), prefix="/openapi")
    yield


app: FastAPI = FastAPI(
    title="Magic Boto Agent API",
    description="OpenAI-compatible chat; tools from tools_api OpenAPI, executed via HTTP.",
    lifespan=lifespan,
)
register_app_error_handler(app)
app.include_router(health_router, prefix="/health")
