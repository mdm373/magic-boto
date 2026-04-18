"""Shared FastMCP construction for streamable HTTP (ASGI) and stdio CLI."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.db import build_async_sqlalchemy_resources, close_pool, get_pool

from .error_middleware import AppMcp
from .tools import register_tools

_logging_configured = False


class _NoHealthFilter(logging.Filter):
    """Drop uvicorn access log records for the /health liveness endpoint."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /health" not in record.getMessage()


def ensure_mcp_logging() -> None:
    """Configure loguru once (asgi and stdio entrypoints both import this package)."""
    global _logging_configured
    if _logging_configured:
        return
    logger.remove()
    logger.add(
        sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper(), backtrace=True, diagnose=True
    )
    logging.getLogger("uvicorn.access").addFilter(_NoHealthFilter())
    _logging_configured = True


def mcp_cors_origins_from_env() -> list[str]:
    """Parse ``TOOLS_MCP_CORS_ORIGINS`` (comma list or ``*``)."""
    raw = os.environ.get("TOOLS_MCP_CORS_ORIGINS", "*").strip()
    if not raw:
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def wrap_streamable_http_app_with_cors(inner: ASGIApp) -> ASGIApp:
    """CORSMiddleware forwards non-http scopes (e.g. lifespan) to the MCP Starlette app."""
    return CORSMiddleware(
        inner,
        allow_origins=mcp_cors_origins_from_env(),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    )


def _register_health_route(mcp: FastMCP[dict[str, Any]]) -> None:
    """Liveness for orchestration (Docker, Compose); same shape as ``serve_http`` ``/health``."""

    async def _health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    mcp.custom_route("/health", methods=["GET"], include_in_schema=False)(_health)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def create_mcp_server(*, streamable_http: bool) -> FastMCP[dict[str, Any]]:
    """Construct FastMCP with tool registration and DB lifespan."""
    ensure_mcp_logging()
    host = os.environ.get("TOOLS_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("TOOLS_MCP_PORT", "8765"))
    # Stateful HTTP keeps MCP sessions in process memory; stale ``mcp-session-id`` after
    # restart, ``--reload``, or another worker → HTTP 404 + JSON-RPC "Session not found".
    # Stateless mode handles each POST independently (no session header required).
    stateless_http = streamable_http and _env_flag("TOOLS_MCP_STATELESS_HTTP")

    app_mcp: AppMcp | None = None

    @asynccontextmanager
    async def mcp_lifespan(_mcp: FastMCP[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        nonlocal app_mcp
        await get_pool()
        assert app_mcp is not None
        app_mcp.sqlalchemy = build_async_sqlalchemy_resources()
        yield {}
        assert app_mcp.sqlalchemy is not None
        await app_mcp.sqlalchemy.engine.dispose()
        app_mcp.sqlalchemy = None
        await close_pool()

    mcp = FastMCP(
        "Magic Boto Tools",
        instructions=(
            "MTG catalog: cards, editions, inventories, tags, sweeps, audits, MTGJSON fetch jobs."
        ),
        lifespan=mcp_lifespan,
        host=host,
        port=port,
        json_response=streamable_http,
        stateless_http=stateless_http,
    )
    app_mcp = AppMcp(mcp)
    register_tools(app_mcp)
    _register_health_route(mcp)
    return mcp
