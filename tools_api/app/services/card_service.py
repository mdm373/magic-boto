"""Card lookup service for MTGJSON cards API."""

from typing import cast

from fastapi_pagination.bases import AbstractPage
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema import Card
from app.api_schema.card_search import CardSearchQuery
from app.repository import CardRepo
from app.services.card_search_query_builder import CardSearchQueryBuilder
from app.services.mapper import CardMapper


class CardService:
    """Card lookup service.

    Mapper and query builder are injected at construction time; DB session is per request.
    """

    def __init__(self, mapper: CardMapper, query_builder: CardSearchQueryBuilder) -> None:
        self._mapper = mapper
        self._query_builder = query_builder
        self._repo = CardRepo()

    async def search_cards(
        self,
        session: AsyncSession,
        query: CardSearchQuery,
    ) -> AbstractPage[Card]:
        """List cards."""
        filters = [
            *self._query_builder.build_predicates(query.filters),
        ]
        page = await self._repo.search_cards(
            session,
            filters=filters,
            distinct_oracle=query.filters.distinct_oracle,
            page_number=query.pagination.page_number,
            page_size=query.pagination.page_size,
            inventory_name=query.filters.inventory_name,
        )
        page.items = [self._mapper.to_response(card) for card in page.items]  # type: ignore[attr-defined]
        return cast(AbstractPage[Card], page)

    async def query_card(
        self,
        session: AsyncSession,
        card_id: str,
    ) -> Card | None:
        """Look up a single card by internal catalog id. Returns None if not found."""
        card = await self._repo.get_by_id(session, card_id)
        if card is None:
            return None
        return self._mapper.to_response(card)
