"""Card lookup service for MTGJSON cards API."""

from collections.abc import Sequence
from typing import Any

from loguru import logger
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    MtgjsonCardIdentifiersModel,
    MtgjsonCardModel,
    MtgjsonCardTypeModel,
)
from app.schema import CardsQuery, MtgjsonCard
from app.services.mapper import CardMapper


class CardService:
    """Card lookup service.

    Mapper is injected at construction time; DB session is provided per request.
    """

    def __init__(self, mapper: CardMapper) -> None:
        self._mapper = mapper

    async def query_cards(
        self,
        session: AsyncSession,
        query: CardsQuery,
    ) -> Sequence[MtgjsonCard]:
        """
        Look up cards. Caller must ensure query is not empty.
        """
        idents = MtgjsonCardIdentifiersModel
        filters: list[Any] = []
        ident_conditions = []
        if query.name is not None:
            filters.append(MtgjsonCardModel.name.ilike(f"%{query.name.strip()}%"))
        if query.card_id is not None:
            ident_conditions.append(idents.card_id == query.card_id)
        if query.oracle_id is not None:
            ident_conditions.append(idents.oracle_id == query.oracle_id)
        if ident_conditions:
            filters.append(MtgjsonCardModel.identifiers.has(or_(*ident_conditions)))
        if query.rarity is not None:
            filters.append(MtgjsonCardModel.rarity == query.rarity)
        if query.set_code is not None:
            filters.append(MtgjsonCardModel.set_code == query.set_code.strip())
        if query.card_type is not None:
            filters.append(
                MtgjsonCardModel.card_types.any(
                    MtgjsonCardTypeModel.card_type == query.card_type.value
                )
            )
        if query.mana_value_lt is not None:
            filters.append(MtgjsonCardModel.mana_value < query.mana_value_lt)
        if query.mana_value_gt is not None:
            filters.append(MtgjsonCardModel.mana_value > query.mana_value_gt)
        if query.mana_value_eq is not None:
            filters.append(MtgjsonCardModel.mana_value == query.mana_value_eq)
        stmt = (
            select(MtgjsonCardModel)
            .options(selectinload(MtgjsonCardModel.card_types))
            .where(and_(*filters))
        )
        logger.debug("query_cards query: {}", query.model_dump())
        result = await session.execute(stmt)
        rows = result.unique().scalars().all()
        return [self._mapper.to_response(card) for card in rows]

    async def query_card(
        self,
        session: AsyncSession,
        card_id: str,
    ) -> MtgjsonCard | None:
        """
        Look up a single card by card_id (printing-specific). Returns None if not found.
        """
        logger.debug("Card lookup: query_card(card_id={})", card_id)
        stmt = (
            select(MtgjsonCardModel)
            .options(selectinload(MtgjsonCardModel.card_types))
            .where(MtgjsonCardModel.identifiers.has(MtgjsonCardIdentifiersModel.card_id == card_id))
        )
        result = await session.execute(stmt)
        card = result.scalars().one_or_none()
        if card is None:
            return None
        return self._mapper.to_response(card)
