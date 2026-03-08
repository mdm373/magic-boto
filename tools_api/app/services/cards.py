"""Card lookup service for MTGJSON cards API."""

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MtgjsonCardIdentifiersModel, MtgjsonCardModel
from app.schema import MtgjsonCard


async def query_card(
    session: AsyncSession,
    scryfall_id: str,
) -> MtgjsonCard | None:
    """
    Look up a single card by Scryfall ID. Returns None if not found.
    """
    logger.debug("Card lookup: query_card(scryfall_id={})", scryfall_id)
    stmt = select(MtgjsonCardModel).where(
        MtgjsonCardModel.identifiers.has(MtgjsonCardIdentifiersModel.scryfall_id == scryfall_id)
    )
    result = await session.execute(stmt)
    card = result.scalars().one_or_none()
    if card is None:
        return None
    identifiers = card.identifiers
    return MtgjsonCard(
        name=card.name or "",
        mana_cost=card.mana_cost,
        set_code=card.set_code,
        scryfall_id=identifiers.scryfall_id if identifiers else None,
        type=card.type,
        rarity=card.rarity,
    )
