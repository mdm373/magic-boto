"""MCP tool registration orchestrator."""

from __future__ import annotations

from .cards_tools import register_cards_tools
from .editions_tools import register_editions_tools
from .error_middleware import AppMcp
from .inventory_tools import register_inventory_tools
from .sweep_tools import register_sweep_tools
from .tags_tools import register_tags_tools


def register_tools(app_mcp: AppMcp) -> None:
    """Register all MCP tools."""
    register_cards_tools(app_mcp)
    register_editions_tools(app_mcp)
    register_inventory_tools(app_mcp)
    register_tags_tools(app_mcp)
    register_sweep_tools(app_mcp)


__all__ = [
    "AppMcp",
    "register_tools",
    "register_cards_tools",
    "register_editions_tools",
    "register_inventory_tools",
    "register_sweep_tools",
    "register_tags_tools",
]
