"""Card lookup service for MTGJSON cards API."""

from collections.abc import Sequence
from typing import Any, cast

from fastapi_pagination import Params
from fastapi_pagination.bases import AbstractPage
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models import MagicBotoCardModel
from app.schema import MtgjsonCard
from app.schema.card_search import CardSearchQuery
from app.services.card_search_query_builder import CardSearchQueryBuilder
from app.services.mapper import CardMapper


def _apply_ordering(stmt: Select[Any], *, distinct_oracle: bool) -> Select[Any]:
    if distinct_oracle:
        return stmt.distinct(MagicBotoCardModel.oracle_id).order_by(
            MagicBotoCardModel.oracle_id.asc(),
            MagicBotoCardModel.name.asc(),
        )
    return stmt.order_by(MagicBotoCardModel.name.asc())


class CardService:
    """Card lookup service.

    Mapper and query builder are injected at construction time; DB session is per request.
    """

    def __init__(self, mapper: CardMapper, query_builder: CardSearchQueryBuilder) -> None:
        self._mapper = mapper
        self._query_builder = query_builder

    async def search_cards(
        self,
        session: AsyncSession,
        query: CardSearchQuery,
    ) -> AbstractPage[MtgjsonCard]:
        """List cards"""
        filters = [
            MagicBotoCardModel.scryfall_id.isnot(None),
            *self._query_builder.build_predicates(query.filters),
        ]

        base = (
            select(MagicBotoCardModel)
            .options(
                selectinload(MagicBotoCardModel.card_types),
                selectinload(MagicBotoCardModel.subtypes),
                selectinload(MagicBotoCardModel.keywords),
                selectinload(MagicBotoCardModel.supertypes),
                selectinload(MagicBotoCardModel.meta),
            )
            .where(and_(*filters))
        )
        stmt = _apply_ordering(base, distinct_oracle=query.filters.distinct_oracle)

        return cast(
            AbstractPage[MtgjsonCard],
            await paginate(
                session,
                stmt,
                params=Params(
                    page=query.pagination.page_number,
                    size=query.pagination.page_size,
                ),
                transformer=lambda items: [self._mapper.to_response(card) for card in items],
            ),
        )

    async def fetch_cards_by_oracle_ids(
        self, session: AsyncSession, oracle_ids: Sequence[str]
    ) -> Sequence[MagicBotoCardModel]:
        """Return one representative card per oracle_id, preserving input order."""
        if not oracle_ids:
            return []
        rows = await session.execute(
            select(MagicBotoCardModel)
            .where(MagicBotoCardModel.oracle_id.in_(oracle_ids))
            .distinct(MagicBotoCardModel.oracle_id)
            .order_by(MagicBotoCardModel.oracle_id, MagicBotoCardModel.card_id)
        )
        by_oracle_id = {card.oracle_id: card for card in rows.scalars()}
        return [by_oracle_id[oid] for oid in oracle_ids if oid in by_oracle_id]

    async def query_card(
        self,
        session: AsyncSession,
        card_id: str,
    ) -> MtgjsonCard | None:
        """Look up a single card by internal catalog id (primary key). Returns None if not found."""
        stmt = (
            select(MagicBotoCardModel)
            .options(
                selectinload(MagicBotoCardModel.card_types),
                selectinload(MagicBotoCardModel.subtypes),
                selectinload(MagicBotoCardModel.keywords),
                selectinload(MagicBotoCardModel.supertypes),
                selectinload(MagicBotoCardModel.meta),
            )
            .where(MagicBotoCardModel.card_id == card_id)
        )
        result = await session.execute(stmt)
        card = result.scalars().one_or_none()
        if card is None:
            return None
        return self._mapper.to_response(card)
