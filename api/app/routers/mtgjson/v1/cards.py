"""MTGJSON v1 cards API: read by Scryfall ID. Delegates to services layer."""

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.schema import MtgjsonCard
from app.services import query_card

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
    card = await query_card(session, scryfall_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card
