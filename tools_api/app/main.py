"""FastAPI app: healthcheck and MTGJSON v1 tool endpoints (OpenAPI-described)."""

import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from .db import close_async_engine, close_pool, get_async_engine, get_pool
from .errors import InternalError, InvalidRequestError
from .routers import v1_router

logger.remove()
_log_fmt = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "{name}:{function}:{line} - <level>{message}</level>"
)
logger.add(sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper(), format=_log_fmt)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await get_pool()
    get_async_engine()
    yield
    await close_async_engine()
    await close_pool()


app: FastAPI = FastAPI(
    title="Magic Boto Tools API",
    description="OpenAPI-described tool endpoints (e.g. card lookup). Consumed by agent-api.",
    lifespan=lifespan,
)

app.include_router(v1_router)


@app.exception_handler(InvalidRequestError)
async def validation_error_handler(request: Request, exc: InvalidRequestError) -> JSONResponse:
    """Convert validator errors into the standard 422 response."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


@app.exception_handler(InternalError)
async def internal_error_handler(request: Request, exc: InternalError) -> JSONResponse:
    logger.exception("Internal error: {}", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Healthcheck."""
    return {"status": "ok"}
