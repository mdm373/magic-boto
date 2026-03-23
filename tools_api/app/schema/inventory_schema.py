"""Request/response schemas for inventory API."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class CreateInventoryRequest(BaseModel):
    """Body to create an inventory."""

    name: str = Field(min_length=1, max_length=500, description="Display name for this collection.")


class InventoryResponse(BaseModel):
    """One inventory."""

    id: uuid.UUID
    name: str


class AddInventoryCardsBody(BaseModel):
    """JSON body for ``POST /v1/inventories/{inventory_id}/cards``."""

    scryfall_ids: list[str] = Field(
        min_length=1,
        description="Scryfall printing ids (Card Unique Printing Identifier).",
    )


class AddInventoryCardsRequest(BaseModel):
    """Merged add-cards input: path ``inventory_id`` + body ``scryfall_ids``.

    Built in the router via ``Depends`` so handlers see one model. The inventory id
    is not repeated in the JSON body.

    If the same Scryfall id appears multiple times, its quantity is incremented.
    """

    inventory_id: uuid.UUID
    scryfall_ids: list[str] = Field(
        min_length=1,
        description="Scryfall printing ids (Card Unique Printing Identifier).",
    )


def build_add_inventory_cards_request(
    inventory_id: uuid.UUID,
    body: AddInventoryCardsBody,
) -> AddInventoryCardsRequest:
    """Combine path ``inventory_id`` and JSON body (HTTP route or MCP tool)."""
    return AddInventoryCardsRequest(inventory_id=inventory_id, scryfall_ids=body.scryfall_ids)
