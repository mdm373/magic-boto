"""MCP card tool registrations."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import cast

import httpx
from mcp.types import ImageContent, ToolAnnotations

from app import SERVICE_ROOT
from app.api_schema import (
    Card,
    CardSearchFilters,
    CardSearchFlags,
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
# Cache stores the base64-encoded MCP payload directly, not raw image bytes — a cache hit is then
# a plain text read straight into the tool response, with no decode/re-encode of the image on
# every call. Nothing else consumes this cache (the plain HTTP image route was removed since MCP
# UI apps can't reach it — see cards_tools.py's get_card_image tool), so the encoded form is fine.
_IMAGE_CACHE_DIR = SERVICE_ROOT / "cache" / "card_images"
# Scryfall calls have no timeout otherwise — a stalled connection (e.g. broken egress) hangs the
# request indefinitely instead of failing fast.
_SCRYFALL_TIMEOUT_SECONDS = 10.0

_card_service = create_card_service()

_SCRYFALL_SEMAPHORE = asyncio.Semaphore(1)
_SCRYFALL_REQUEST_DELAY = 1.0  # minimum seconds between image requests
_scryfall_last_fetch: float = 0.0
_SCRYFALL_HEADERS = {"User-Agent": "magic-boto/1.0 (personal collection tool)"}


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


async def _fetch_card_image_base64(scryfall_id: str) -> str:
    """Return the base64-encoded JPEG for a Scryfall ID, using the shared cache."""
    global _scryfall_last_fetch
    cache_path = _IMAGE_CACHE_DIR / f"{scryfall_id}.b64"
    if cache_path.exists():
        return await asyncio.to_thread(cache_path.read_text, encoding="ascii")
    async with _SCRYFALL_SEMAPHORE:
        # Re-check cache in case another concurrent call wrote it while we waited.
        if cache_path.exists():
            return await asyncio.to_thread(cache_path.read_text, encoding="ascii")
        wait = _SCRYFALL_REQUEST_DELAY - (asyncio.get_event_loop().time() - _scryfall_last_fetch)
        if wait > 0:
            await asyncio.sleep(wait)
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=_SCRYFALL_HEADERS,
            timeout=_SCRYFALL_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(_SCRYFALL_IMAGE_URL.format(scryfall_id=scryfall_id))
        _scryfall_last_fetch = asyncio.get_event_loop().time()
        response.raise_for_status()
        encoded = base64.standard_b64encode(response.content).decode("ascii")

        def _write_cache() -> None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(encoded, encoding="ascii")

        await asyncio.to_thread(_write_cache)
    return encoded


def register_cards_tools(app_mcp: AppMcp) -> None:
    """Register card MCP tools and bundled UI resources."""

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
            "Search the catalog with optional filters (AND). "
            "Use flags.verbose=true for full card fields; default is a minimal card row."
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
        flags: CardSearchFlags = CardSearchFlags(),
    ) -> CardsPage:
        query = CardSearchQuery(filters=filters, pagination=pagination, flags=flags)
        async with app_mcp.session() as session:
            page = await _card_service.search_cards(session, query)
            return cast(CardsPage, page)

    @app_mcp.tool(
        name="get_card",
        description=(
            "Get one card by internal ``card_id`` (one row per printing). "
            "Use verbose=true for full fields; default is minimal."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": CARD_RESOURCE_URI}},
    )
    async def get_card(card_id: str, verbose: bool = False) -> Card:
        async with app_mcp.session() as session:
            card = await _card_service.query_card(session, card_id, summary_only=not verbose)
            if card is None:
                raise NotFoundError("Card not found")
            return card

    @app_mcp.tool(
        name="get_card_image",
        description="Fetch JPEG artwork for a Scryfall printing id (UUID).",
    )
    async def show_card_image(scryfall_id: str) -> ImageContent:
        data = await _fetch_card_image_base64(scryfall_id)
        return ImageContent(type="image", data=data, mimeType="image/jpeg")
