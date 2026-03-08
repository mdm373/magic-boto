"""MTGJSON v1 cards API: read by Scryfall ID. operation_id for agent OpenAPI→tools."""

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.schema import MtgjsonCard
from app.services import query_card

cards_router = APIRouter(
    prefix="/cards",
    tags=["mtgjson_cards"],
    dependencies=[Depends(inject_session_into_request)],
)


@cards_router.get(
    "/{scryfall_id}",
    response_model=MtgjsonCard,
    operation_id="get_card",
    summary="Get card by Scryfall ID",
)
async def get_card_by_scryfall_id(scryfall_id: str, request: Request) -> MtgjsonCard:
    """
    Look up a Magic: The Gathering card by its Scryfall ID (UUID with dashes).
    Path param: Scryfall UUID (e.g. 7dx-xxxxx-xxxxxx-xxxx-xx).
    """
    session = get_request_session(request)
    card = await query_card(session, scryfall_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card
