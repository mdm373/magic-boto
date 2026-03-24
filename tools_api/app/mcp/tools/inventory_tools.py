"""MCP inventory tool registrations."""

from __future__ import annotations

import uuid
from typing import Any

from app.db import get_async_session_factory
from app.errors import NotFoundError
from app.mcp.error_middleware import AppMcp
from app.schema import (
    AddInventoryCardsBody,
    CreateInventoryRequest,
    build_add_inventory_cards_request,
)
from app.services import create_inventory_service
from app.validators import InventoryCardsValidator

_inventory_service = create_inventory_service()
_inventory_cards_validator = InventoryCardsValidator()


def register_inventory_tools(app_mcp: AppMcp) -> None:
    """Register inventory MCP tools."""

    @app_mcp.tool(
        name="create_inventory",
        description="Create a named inventory (collection).",
    )
    async def create_inventory(body: CreateInventoryRequest) -> dict[str, Any]:
        factory = get_async_session_factory()
        async with factory() as session:
            inv = await _inventory_service.create_inventory(session, body.name)
            return inv.model_dump(mode="json")

    @app_mcp.tool(
        name="delete_inventory",
        description="Delete an inventory and all linked cards. Errors if the id is unknown.",
    )
    async def delete_inventory(inventory_id: uuid.UUID) -> dict[str, bool]:
        factory = get_async_session_factory()
        async with factory() as session:
            deleted = await _inventory_service.delete_inventory(session, inventory_id)
            if not deleted:
                raise NotFoundError("Inventory not found")
            return {"ok": True}

    @app_mcp.tool(
        name="add_inventory_cards",
        description="Add printings to an inventory by Scryfall printing ids (UUID strings).",
    )
    async def add_inventory_cards(
        inventory_id: uuid.UUID,
        body: AddInventoryCardsBody,
    ) -> dict[str, bool]:
        factory = get_async_session_factory()
        async with factory() as session:
            merged = build_add_inventory_cards_request(inventory_id, body)
            resolved = await _inventory_cards_validator.validate_add_inventory_cards(
                session,
                merged,
            )
            await _inventory_service.add_cards_by_card_id(session, merged.inventory_id, resolved)
            return {"ok": True}
