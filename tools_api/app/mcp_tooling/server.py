"""Shared FastMCP construction for streamable HTTP (ASGI) and stdio CLI."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from loguru import logger
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.db import build_async_sqlalchemy_resources, close_pool, get_pool

from .auth import OidcAuthProvider, oidc_auth_settings_from_env
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


@asynccontextmanager
async def _db_resources(app_mcp: AppMcp) -> AsyncIterator[None]:
    """Own the asyncpg pool and SQLAlchemy engine for the life of the process."""
    await get_pool()
    app_mcp.sqlalchemy = build_async_sqlalchemy_resources()
    try:
        yield
    finally:
        await app_mcp.sqlalchemy.engine.dispose()
        app_mcp.sqlalchemy = None
        await close_pool()


def _build_mcp_server(
    *,
    streamable_http: bool,
    lifespan: Callable[[FastMCP[dict[str, Any]]], AbstractAsyncContextManager[dict[str, Any]]]
    | None,
) -> tuple[FastMCP[dict[str, Any]], AppMcp]:
    """Construct FastMCP with tool registration; the caller decides who owns DB resources."""
    ensure_mcp_logging()
    host = os.environ.get("TOOLS_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("TOOLS_MCP_PORT", "8765"))
    # Stateful HTTP keeps MCP sessions in process memory; stale ``mcp-session-id`` after
    # restart, ``--reload``, or another worker → HTTP 404 + JSON-RPC "Session not found".
    # Stateless mode handles each POST independently (no session header required).
    stateless_http = streamable_http and _env_flag("TOOLS_MCP_STATELESS_HTTP")

    # Bearer-token auth is a resource-server concern (RFC 9728): only meaningful over
    # streamable HTTP, where a client can present an ``Authorization`` header. stdio has
    # no such transport-level credential, so auth stays off there regardless of env.
    oidc_settings = oidc_auth_settings_from_env() if streamable_http else None
    token_verifier = OidcAuthProvider(oidc_settings) if oidc_settings else None
    auth_settings = (
        AuthSettings(
            issuer_url=oidc_settings.issuer_url,  # type: ignore[arg-type]
            resource_server_url=oidc_settings.resource_server_url,  # type: ignore[arg-type]
            required_scopes=list(oidc_settings.required_scopes) or None,
        )
        if oidc_settings
        else None
    )
    if oidc_settings:
        logger.info("MCP auth enabled: issuer={}", oidc_settings.issuer_url)

    mcp = FastMCP(
        "Magic Boto Tools",
        instructions=(
            "Magic: The Gathering card catalog and the user's card collection.\n"
            "Tools named `ui_*` render an interactive UI for the user; call them only to show "
            "the user something, and don't repeat their JSON output. Use the plain tools for "
            "research."
        ),
        lifespan=lifespan,
        host=host,
        port=port,
        json_response=streamable_http,
        stateless_http=stateless_http,
        token_verifier=token_verifier,
        auth=auth_settings,
    )
    app_mcp = AppMcp(mcp)
    register_tools(app_mcp)
    _register_health_route(mcp)
    return mcp, app_mcp


def create_stdio_mcp_server() -> FastMCP[dict[str, Any]]:
    """FastMCP for stdio: one server run per process, so its lifespan owns DB resources."""
    app_mcp: AppMcp | None = None

    @asynccontextmanager
    async def mcp_lifespan(_mcp: FastMCP[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        assert app_mcp is not None
        async with _db_resources(app_mcp):
            yield {}

    mcp, app_mcp = _build_mcp_server(streamable_http=False, lifespan=mcp_lifespan)
    return mcp


def create_streamable_http_app() -> ASGIApp:
    """MCP streamable HTTP ASGI app with DB resources tied to the ASGI app lifespan.

    FastMCP re-enters its own ``lifespan`` for every stateless HTTP request, so DB setup and
    teardown can't live there: concurrent requests would dispose a shared engine out from
    under each other. The Starlette app lifespan runs exactly once per process instead.
    """
    mcp, app_mcp = _build_mcp_server(streamable_http=True, lifespan=None)
    starlette_app: Starlette = mcp.streamable_http_app()
    inner_lifespan = starlette_app.router.lifespan_context

    @asynccontextmanager
    async def app_lifespan(app: Starlette) -> AsyncIterator[None]:
        async with _db_resources(app_mcp), inner_lifespan(app):
            yield

    starlette_app.router.lifespan_context = app_lifespan
    return wrap_streamable_http_app_with_cors(starlette_app)
