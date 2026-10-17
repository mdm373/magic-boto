"""MCP streamable HTTP ASGI app for Uvicorn."""

from __future__ import annotations

from app.mcp_tooling.server import create_streamable_http_app, ensure_mcp_logging

ensure_mcp_logging()

app = create_streamable_http_app()
