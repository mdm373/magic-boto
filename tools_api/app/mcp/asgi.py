"""MCP streamable HTTP ASGI app for Uvicorn."""

from __future__ import annotations

from .server import (
    create_mcp_server,
    ensure_mcp_logging,
    wrap_streamable_http_app_with_cors,
)

ensure_mcp_logging()

_mcp = create_mcp_server(streamable_http=True)

app = wrap_streamable_http_app_with_cors(_mcp.streamable_http_app())
