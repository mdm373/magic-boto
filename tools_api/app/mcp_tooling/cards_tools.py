"""MCP card tool registrations."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import cast

import httpx
from mcp.types import ImageContent, ToolAnnotations

from app import SERVICE_ROOT
from app.api_schema import (
    Card,
    CardSearchFilters,
    CardSearchPagination,
    CardSearchQuery,
    CardsPage,
)
from app.errors import NotFoundError
from app.services import create_card_service

from .error_middleware import AppMcp

CARD_RESOURCE_URI = "ui://magic-boto/card"
CARD_CAROUSEL_RESOURCE_URI = "ui://magic-boto/card-carousel"

_UI_DIST = Path(__file__).parent / "ui_dist"
_UI_MIME_TYPE = "text/html;profile=mcp-app"
_FALLBACK_HTML = (
    "<!doctype html><html><body style='font-family:sans-serif;padding:1rem'>"
    "<p>UI not built. Run <code>npm run build</code> inside "
    "<code>tools-ui/</code>.</p></body></html>"
)
_SCRYFALL_IMAGE_URL = "https://api.scryfall.com/cards/{scryfall_id}?format=image"
_IMAGE_CACHE_DIR = SERVICE_ROOT / "cache" / "card_images"

_card_service = create_card_service()


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


async def _fetch_card_image(scryfall_id: str) -> bytes:
    """Return image bytes for a Scryfall ID, using the shared cache."""
    cache_path = _IMAGE_CACHE_DIR / f"{scryfall_id}.jpg"
    if cache_path.exists():
        return cache_path.read_bytes()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(_SCRYFALL_IMAGE_URL.format(scryfall_id=scryfall_id))
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)
    return response.content


def register_cards_tools(app_mcp: AppMcp) -> None:
    """Register card MCP tools and UI resource."""

    @app_mcp.mcp.resource(CARD_RESOURCE_URI, name="card_ui", mime_type=_UI_MIME_TYPE)
    def card_ui() -> str:
        return _read_ui("pages/card.html")

    @app_mcp.mcp.resource(
        CARD_CAROUSEL_RESOURCE_URI,
        name="card_carousel_ui",
        mime_type=_UI_MIME_TYPE,
    )
    def card_carousel_ui() -> str:
        return _read_ui("pages/card-carousel.html")

    @app_mcp.tool(
        name="search_cards",
        description=(
            "Search MTG cards with explicit optional filters. "
            "All provided filters are combined with AND."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": CARD_CAROUSEL_RESOURCE_URI}},
    )
    async def search_cards(
        filters: CardSearchFilters = CardSearchFilters(),
        pagination: CardSearchPagination = CardSearchPagination(),
    ) -> CardsPage:
        query = CardSearchQuery(filters=filters, pagination=pagination)
        async with app_mcp.session() as session:
            page = await _card_service.search_cards(session, query)
            return cast(CardsPage, page)

    @app_mcp.tool(
        name="get_card",
        description=(
            "Get one card by internal catalog id (``card_id`` from search results). "
            "Unique per printing and avoids the ambiguity of Scryfall id on flip/split cards."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": CARD_RESOURCE_URI}},
    )
    async def get_card(card_id: str) -> Card:
        async with app_mcp.session() as session:
            card = await _card_service.query_card(session, card_id)
            if card is None:
                raise NotFoundError("Card not found")
            return card

    @app_mcp.tool(
        name="get_card_image",
        description="Renders a Magic card image in the UI by Scryfall ID.",
    )
    async def show_card_image(scryfall_id: str) -> ImageContent:
        image_bytes = await _fetch_card_image(scryfall_id)
        data = base64.standard_b64encode(image_bytes).decode()
        return ImageContent(type="image", data=data, mimeType="image/jpeg")
