"""MCP inventory tool registrations."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from app.errors import InvalidRequestError, NotFoundError
from app.repository import InventoryRepo, canonical_name
from app.services import DEFAULT_INVENTORY_NAME, create_inventory_service

from .error_middleware import AppMcp

_inventory_service = create_inventory_service()
_inv_repo = InventoryRepo()


def _inventory_name_or_error(raw: str) -> str:
    cn = canonical_name(raw)
    if not cn:
        raise InvalidRequestError("Inventory name is required.")
    if cn == DEFAULT_INVENTORY_NAME:
        raise InvalidRequestError(
            "Cannot modify the reserved inventory _default via MCP; use import for that collection."
        )
    return cn


def register_inventory_tools(app_mcp: AppMcp) -> None:
    """Register inventory MCP tools."""

    @app_mcp.tool(
        name="list_inventory_names",
        description=(
            "List names of card inventories (collections) in the database. "
            "Use with card search ``inventory_name`` (canonical lowercase names)."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_inventory_names() -> list[str]:
        async with app_mcp.session() as session:
            return await _inv_repo.list_names(session)

    @app_mcp.tool(
        name="create_inventory",
        description=(
            "Create a named inventory collection if it does not exist, or return the existing one. "
            "Use this to persist deck lists and other constructed lists: "
            "pick a stable name per deck "
            "so ``inventory_name`` in card search can filter to that collection. "
            "Names are stored trimmed and lowercased. "
            "The reserved name _default cannot be created here."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def create_inventory(
        name: Annotated[
            str,
            Field(
                description=(
                    "Collection name (e.g. deck title). Persist decks under distinct names "
                    "so searches can target them."
                ),
            ),
        ],
    ) -> str:
        cn = canonical_name(name)
        if not cn:
            raise InvalidRequestError("Inventory name is required.")
        if cn == DEFAULT_INVENTORY_NAME:
            raise InvalidRequestError(
                "Cannot create the reserved inventory name via MCP; use import for _default."
            )
        async with app_mcp.session() as session:
            inv = await _inv_repo.get_or_create(session, name)
            return inv.name

    @app_mcp.tool(
        name="add_inventory_cards",
        description=(
            "Add catalog printings to an inventory by Scryfall printing id "
            "(each list entry adds one copy; duplicates increase quantity). "
            "Returns only ok. The reserved name _default is not allowed."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def add_inventory_cards(
        inventory_name: Annotated[
            str,
            Field(description="Target inventory (canonical name)."),
        ],
        scryfall_ids: Annotated[
            list[str],
            Field(
                description="Scryfall printing ids (UUID per printing); one copy per element.",
            ),
        ],
    ) -> Literal["ok"]:
        _inventory_name_or_error(inventory_name)
        async with app_mcp.session() as session:
            inv = await _inv_repo.get_by_name(session, inventory_name)
            if inv is None:
                raise NotFoundError("Inventory not found")
            await _inventory_service.add_cards_by_scryfall_ids(session, inv.id, scryfall_ids)
        return "ok"

    @app_mcp.tool(
        name="remove_inventory_cards",
        description=(
            "Remove catalog printings from an inventory by Scryfall printing id "
            "(each list entry removes one copy; duplicates remove more). "
            "Counts cannot go below zero. Returns only ok. "
            "The reserved name _default is not allowed."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def remove_inventory_cards(
        inventory_name: Annotated[
            str,
            Field(description="Target inventory (canonical name)."),
        ],
        scryfall_ids: Annotated[
            list[str],
            Field(
                description="Scryfall printing ids; one copy removed per element.",
            ),
        ],
    ) -> Literal["ok"]:
        _inventory_name_or_error(inventory_name)
        async with app_mcp.session() as session:
            inv = await _inv_repo.get_by_name(session, inventory_name)
            if inv is None:
                raise NotFoundError("Inventory not found")
            await _inventory_service.remove_cards_by_scryfall_ids(session, inv.id, scryfall_ids)
        return "ok"
