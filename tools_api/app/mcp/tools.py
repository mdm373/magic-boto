"""MCP tool handlers: same domain services as :mod:`app.http` routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi_pagination import Params
from mcp.server.fastmcp import FastMCP

from app.db import get_async_session_factory
from app.errors import NotFoundError
from app.schema import (
    AddInventoryCardsBody,
    CardQueryCondition,
    CardQueryRequest,
    CreateInventoryRequest,
    EditionsQuery,
    MtgjsonCard,
    MtgjsonEdition,
    build_add_inventory_cards_request,
)
from app.services import create_card_service, create_edition_service, create_inventory_service
from app.validators import EditionQueryValidator, InventoryCardsValidator

_card_service = create_card_service()
_edition_service = create_edition_service()
_inventory_service = create_inventory_service()
_edition_validator = EditionQueryValidator()
_inventory_cards_validator = InventoryCardsValidator()


def register_tools(mcp: FastMCP[Any]) -> None:
    """Register tools on the given FastMCP server (names align with OpenAPI operation_id)."""

    @mcp.tool(
        name="search_cards",
        description=(
            "Structured search for MTG cards (conditions combined with AND). "
            "Same fields as the HTTP POST body: pass conditions, page_size, page_number "
            "as top-level arguments (not wrapped in a body object)."
        ),
    )
    async def search_cards(
        conditions: list[CardQueryCondition],
        page_size: int = 100,
        page_number: int = 1,
    ) -> dict[str, Any]:
        body = CardQueryRequest(
            conditions=conditions,
            page_size=page_size,
            page_number=page_number,
        )
        factory = get_async_session_factory()
        async with factory() as session:
            params = Params(page=body.page_number, size=body.page_size)
            page = await _card_service.search_cards(session, body, params)
            return page.model_dump(mode="json")

    @mcp.tool(
        name="get_card",
        description="Get one card by printing-specific card_id (MTGJSON identifier).",
    )
    async def get_card(card_id: str) -> MtgjsonCard:
        factory = get_async_session_factory()
        async with factory() as session:
            card = await _card_service.query_card(session, card_id)
            if card is None:
                raise ValueError("Card not found")
            return card

    @mcp.tool(
        name="list_editions",
        description="List MTG editions (sets); filter by exact set_code and/or fuzzy name.",
    )
    async def list_editions(
        set_code: str | None = None,
        name: str | None = None,
    ) -> list[MtgjsonEdition]:
        query = EditionsQuery(set_code=set_code, name=name)
        query = _edition_validator.validate_edition_query(query)
        factory = get_async_session_factory()
        async with factory() as session:
            editions = await _edition_service.query_editions(session, query)
            return list(editions)

    @mcp.tool(
        name="get_edition",
        description="Get one edition (set) by set code.",
    )
    async def get_edition(set_code: str) -> MtgjsonEdition:
        factory = get_async_session_factory()
        async with factory() as session:
            edition = await _edition_service.get_edition(session, set_code)
            if edition is None:
                raise ValueError("Edition not found")
            return edition

    @mcp.tool(
        name="create_inventory",
        description="Create a named inventory (collection).",
    )
    async def create_inventory(body: CreateInventoryRequest) -> dict[str, Any]:
        factory = get_async_session_factory()
        async with factory() as session:
            inv = await _inventory_service.create_inventory(session, body.name)
            return inv.model_dump(mode="json")

    @mcp.tool(
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

    @mcp.tool(
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
