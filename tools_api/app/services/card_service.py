"""Card lookup service for MTGJSON cards API."""

from typing import cast

from fastapi_pagination import Params
from fastapi_pagination.bases import AbstractPage
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MtgjsonCardIdentifiersModel, MtgjsonCardModel
from app.schema import MtgjsonCard
from app.schema.card_query import CardQueryRequest
from app.services.card_query_compile import SqlPredicate, compile_conditions
from app.services.mapper import CardMapper


class CardService:
    """Card lookup service.

    Mapper is injected at construction time; DB session is provided per request.
    """

    def __init__(self, mapper: CardMapper) -> None:
        self._mapper = mapper

    async def search_cards(
        self,
        session: AsyncSession,
        body: CardQueryRequest,
        params: Params,
    ) -> AbstractPage[MtgjsonCard]:
        """List cards"""
        filters: list[SqlPredicate] = [*compile_conditions(body.conditions)]
        stmt = (
            select(MtgjsonCardModel)
            .options(
                selectinload(MtgjsonCardModel.card_types),
                selectinload(MtgjsonCardModel.card_subtypes),
                selectinload(MtgjsonCardModel.card_supertypes),
            )
            .where(and_(*filters))
        )
        return cast(
            AbstractPage[MtgjsonCard],
            await paginate(
                session,
                stmt,
                params=params,
                transformer=lambda items: [self._mapper.to_response(card) for card in items],
            ),
        )

    async def query_card(
        self,
        session: AsyncSession,
        card_id: str,
    ) -> MtgjsonCard | None:
        """
        Look up a single card by card_id (printing-specific). Returns None if not found.
        """
        stmt = (
            select(MtgjsonCardModel)
            .options(
                selectinload(MtgjsonCardModel.card_types),
                selectinload(MtgjsonCardModel.card_subtypes),
                selectinload(MtgjsonCardModel.card_supertypes),
            )
            .where(MtgjsonCardModel.identifiers.has(MtgjsonCardIdentifiersModel.card_id == card_id))
        )
        result = await session.execute(stmt)
        card = result.scalars().one_or_none()
        if card is None:
            return None
        return self._mapper.to_response(card)
