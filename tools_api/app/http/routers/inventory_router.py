"""Inventory API: create/delete collections; add printings by Scryfall ids."""

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.errors import NotFoundError
from app.schema import (
    AddInventoryCardsBody,
    CreateInventoryRequest,
    InventoryResponse,
    build_add_inventory_cards_request,
)
from app.services import create_inventory_service
from app.validators import InventoryCardsValidator


def create_inventory_router() -> APIRouter:
    """Factory for inventory routes (closure-based DI)."""
    service = create_inventory_service()
    validator = InventoryCardsValidator()
    router = APIRouter(
        prefix="/inventories",
        tags=["inventory"],
        dependencies=[Depends(inject_session_into_request)],
    )

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_inventory",
        summary="Create an inventory",
    )
    async def create_inventory(
        body: CreateInventoryRequest,
        request: Request,
    ) -> InventoryResponse:
        session = get_request_session(request)
        return await service.create_inventory(session, body.name)

    @router.delete(
        "/{inventory_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_inventory",
        summary="Delete an inventory and all linked cards",
    )
    async def delete_inventory(inventory_id: uuid.UUID, request: Request) -> Response:
        session = get_request_session(request)
        deleted = await service.delete_inventory(session, inventory_id)
        if not deleted:
            raise NotFoundError("Inventory not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/{inventory_id}/cards",
        operation_id="add_inventory_cards",
        summary="Add printings by Scryfall ids",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def add_cards(
        inventory_id: uuid.UUID,
        body: AddInventoryCardsBody,
        request: Request,
    ) -> Response:
        session = get_request_session(request)
        cards = build_add_inventory_cards_request(inventory_id, body)
        resolved = await validator.validate_add_inventory_cards(session, cards)
        await service.add_cards_by_card_id(
            session,
            cards.inventory_id,
            resolved,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
