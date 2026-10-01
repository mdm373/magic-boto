"""Card lookup service for MTGJSON cards API."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema import Card
from app.api_schema.card_search import CardSearchQuery
from app.models import CardModel
from app.repository import CardRepo, Page
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

    def _map_page_items(self, items: Sequence[CardModel], *, summary_only: bool) -> Sequence[Card]:
        if summary_only:
            return [self._mapper.to_response_compact(item) for item in items]
        return [self._mapper.to_response(item) for item in items]

    async def search_cards(
        self,
        session: AsyncSession,
        query: CardSearchQuery,
    ) -> Page[Card]:
        """List cards."""
        filters = [
            *self._query_builder.build_predicates(query.filters),
        ]
        page = await self._repo.search_cards(
            session,
            filters=filters,
            distinct_oracle=query.flags.distinct_oracle,
            page_number=query.pagination.page_number,
            page_size=query.pagination.page_size,
            inventory_name=query.filters.inventory_name,
        )
        return Page(
            items=self._map_page_items(page.items, summary_only=not query.flags.verbose),
            total=page.total,
            page_number=page.page_number,
            page_size=page.page_size,
        )

    async def query_card(
        self,
        session: AsyncSession,
        card_id: str,
        *,
        summary_only: bool = False,
    ) -> Card | None:
        """Look up a single card by internal catalog id. Returns None if not found."""
        card = await self._repo.get_by_id(session, card_id)
        if card is None:
            return None
        if summary_only:
            return self._mapper.to_response_compact(card)
        return self._mapper.to_response(card)
