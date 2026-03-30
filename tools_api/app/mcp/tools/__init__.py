"""MCP tools package: resource-oriented tool registration modules."""

from __future__ import annotations

from app.mcp.error_middleware import AppMcp

from .cards_tools import register_cards_tools
from .editions_tools import register_editions_tools
from .inventory_tools import register_inventory_tools
from .tags_tools import register_tags_tools


def register_tools(app_mcp: AppMcp) -> None:
    """Register all MCP tools."""

    register_cards_tools(app_mcp)
    register_editions_tools(app_mcp)
    register_inventory_tools(app_mcp)
    register_tags_tools(app_mcp)


__all__ = [
    "AppMcp",
    "register_tools",
    "register_cards_tools",
    "register_editions_tools",
    "register_inventory_tools",
    "register_tags_tools",
]
