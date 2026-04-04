"""MCP card tool registrations."""

from __future__ import annotations

from typing import cast

from mcp.types import ToolAnnotations

from app.api_schema import (
    Card,
    CardSearchFilters,
    CardSearchPagination,
    CardSearchQuery,
    CardsPage,
)
from app.db import get_async_session_factory
from app.errors import NotFoundError
from app.services import create_card_service

from .error_middleware import AppMcp

_card_service = create_card_service()


def register_cards_tools(app_mcp: AppMcp) -> None:
    """Register card MCP tools."""

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
    )
    async def search_cards(
        filters: CardSearchFilters = CardSearchFilters(),
        pagination: CardSearchPagination = CardSearchPagination(),
    ) -> CardsPage:
        query = CardSearchQuery(filters=filters, pagination=pagination)
        factory = get_async_session_factory()
        async with factory() as session:
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
    )
    async def get_card(card_id: str) -> Card:
        factory = get_async_session_factory()
        async with factory() as session:
            card = await _card_service.query_card(session, card_id)
            if card is None:
                raise NotFoundError("Card not found")
            return card
