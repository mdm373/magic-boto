"""Stdio MCP entrypoint."""

from __future__ import annotations

from app.mcp_tooling.server import create_mcp_server, ensure_mcp_logging


def main() -> None:
    ensure_mcp_logging()
    server = create_mcp_server(streamable_http=False)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
