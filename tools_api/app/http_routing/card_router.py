"""MTGJSON v1 cards API: search (POST) and get-by-scryfall_id. OpenAPI->tools."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi_pagination.bases import AbstractPage
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema import Card, CardSearchQuery, CardsPage
from app.db import get_async_session
from app.services import create_card_service


def create_card_router() -> APIRouter:
    """Factory for MTGJSON cards routes."""

    service = create_card_service()
    router = APIRouter(
        prefix="/cards",
        tags=["mtgjson_cards"],
    )

    @router.post(
        "",
        response_model=CardsPage,
        operation_id="search_cards",
        summary="Search cards (POST)",
        description=("Structured search for cards."),
    )
    async def search_cards(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        body: CardSearchQuery,
    ) -> AbstractPage[Card]:
        """Run :meth:`CardService.search_cards` with explicit filters + pagination."""
        return await service.search_cards(session, body)

    @router.get(
        "/{card_id}",
        response_model=Card,
        operation_id="get_card",
        summary="Get one card by internal catalog id.",
    )
    async def get_card_by_id(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        card_id: Annotated[str, Path()],
    ) -> Card:
        """
        Get one card by internal catalog id (primary key, unique per printing).
        Use ``card_id`` from search results. For all printings of the same oracle,
        search with an ``oracle_id`` filter instead.
        """
        card = await service.query_card(session, card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Card not found")
        return card

    return router
