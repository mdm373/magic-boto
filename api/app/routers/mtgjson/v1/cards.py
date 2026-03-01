"""MTGJSON v1 cards API: read by Scryfall ID."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.models import MtgjsonCardIdentifiersModel, MtgjsonCardModel
from app.schema import MtgjsonCard

router = APIRouter(
    prefix="/cards",
    tags=["cards"],
    dependencies=[Depends(inject_session_into_request)],
)


@router.get("/{scryfall_id}", response_model=MtgjsonCard)
async def get_card_by_scryfall_id(scryfall_id: str, request: Request) -> MtgjsonCard:
    """
    Get a single card by Scryfall ID (RESTful read).

    Path param format: Scryfall UUID with dashes (e.g. 7dx-xxxxx-xxxxxx-xxxx-xx).
    """
    session = get_request_session(request)
    stmt = (
        select(MtgjsonCardModel)
        .join(
            MtgjsonCardIdentifiersModel,
            MtgjsonCardModel.uuid == MtgjsonCardIdentifiersModel.uuid,
        )
        .where(MtgjsonCardIdentifiersModel.scryfall_id == scryfall_id)
    )
    result = await session.execute(stmt)
    card = result.scalars().one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    identifiers = card.identifiers
    return MtgjsonCard(
        name=card.name or "",
        mana_cost=card.mana_cost,
        set_code=card.set_code,
        scryfall_id=identifiers.scryfall_id if identifiers else None,
        type=card.type,
        rarity=card.rarity,
    )
