"""MTGJSON v1 cards API: search (POST) and get-by-scryfall_id. OpenAPI->tools."""

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import FileResponse
from fastapi_pagination.bases import AbstractPage
from sqlalchemy.ext.asyncio import AsyncSession

from app import SERVICE_ROOT
from app.api_schema import Card, CardSearchQuery, CardsPage
from app.db import get_async_session
from app.services import create_card_service

_IMAGE_CACHE_DIR = SERVICE_ROOT / "cache" / "card_images"
_SCRYFALL_IMAGE_URL = "https://api.scryfall.com/cards/{scryfall_id}?format=image"


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


def create_card_image_router() -> APIRouter:
    """Factory for the Scryfall card image proxy route (no DB session needed)."""

    router = APIRouter(tags=["card_images"])

    @router.get(
        "/card_images/{scryfall_id}.jpg",
        response_class=FileResponse,
        operation_id="get_card_image",
        summary="Get card image by Scryfall ID",
        description="Returns a JPEG image for the given Scryfall ID. Cached on first fetch.",
    )
    async def get_card_image(scryfall_id: str) -> FileResponse:
        cache_path = _IMAGE_CACHE_DIR / f"{scryfall_id}.jpg"

        if not cache_path.exists():
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(_SCRYFALL_IMAGE_URL.format(scryfall_id=scryfall_id))
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Card image not found")

            def _write_cache() -> None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(response.content)

            await asyncio.to_thread(_write_cache)

        return FileResponse(cache_path, media_type="image/jpeg")

    return router
