"""MTGJSON v1 cards API: search (POST) and get-by-scryfall_id. OpenAPI->tools."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination.bases import AbstractPage
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.schema import CardSearchQuery, CardsPage, MtgjsonCard
from app.services import create_card_service


def create_card_router() -> APIRouter:
    """
    Factory for MTGJSON cards routes.

    Session is injected per request via ``inject_session_into_request``.
    """

    service = create_card_service()
    router = APIRouter(
        prefix="/cards",
        tags=["mtgjson_cards"],
        dependencies=[Depends(inject_session_into_request)],
    )

    @router.post(
        "",
        response_model=CardsPage,
        operation_id="search_cards",
        summary="Search cards (POST)",
        description=("Structured search for cards."),
    )
    async def search_cards(
        request: Request,
        body: CardSearchQuery,
    ) -> AbstractPage[MtgjsonCard]:
        """Run :meth:`CardService.search_cards` with explicit filters + pagination."""
        session = get_request_session(request)
        return await service.search_cards(session, body)

    @router.get(
        "/{scryfall_id}",
        response_model=MtgjsonCard,
        operation_id="get_card",
        summary="Get one card by Scryfall printing id.",
    )
    async def get_card_by_scryfall_id(scryfall_id: str, request: Request) -> MtgjsonCard:
        """
        Get one card by Scryfall printing id (UUID). For other printings of the same
        oracle, use **POST** search with a condition on ``oracle_id`` (not this path).
        """
        session = get_request_session(request)
        card = await service.query_card(session, scryfall_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Card not found")
        return card

    return router
