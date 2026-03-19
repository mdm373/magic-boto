"""MTGJSON v1 cards API: read by card_id or query by oracle_id. OpenAPI→tools."""

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.models import CardRarity, CardType
from app.schema import CardsQuery, MtgjsonCard, allowed_values_description
from app.services import create_card_service
from app.validators import CardQueryValidator


def create_card_router(validator: CardQueryValidator) -> APIRouter:
    """
    Factory for MTGJSON cards routes.

    Uses closure-based DI for the validator instance (instead of `Depends(...)`)
    to keep route signatures clean and dependencies explicit.
    """

    service = create_card_service()
    router = APIRouter(
        prefix="/cards",
        tags=["mtgjson_cards"],
        dependencies=[Depends(inject_session_into_request)],
    )

    @router.get(
        "",
        response_model=list[MtgjsonCard],
        operation_id="list_cards",
        summary="Search for cards",
    )
    async def list_cards(
        request: Request,
        name: str | None = Query(
            None,
            min_length=1,
            description="Fuzzy search on card name (case-insensitive substring).",
        ),
        card_id: str | None = Query(None, description="Card Unique Printing Identifier"),
        oracle_id: str | None = Query(
            None, description="Card Definition (Cross Printing) Identifier"
        ),
        rarity: CardRarity | None = Query(
            None,
            description=f"Printing rarity. {allowed_values_description(CardRarity)}",
        ),
        set_code: str | None = Query(None, min_length=1, description="Edition/set code (e.g. M21)"),
        card_type: CardType | None = Query(
            None,
            description=f"Filter by standard card type. {allowed_values_description(CardType)}",
        ),
        mana_value_lt: int | None = Query(None, description="Filter by mana value < this."),
        mana_value_gt: int | None = Query(None, description="Filter by mana value > this."),
        mana_value_eq: int | None = Query(None, description="Filter by mana value == this."),
    ) -> list[MtgjsonCard]:
        query = CardsQuery(
            name=name,
            card_id=card_id,
            oracle_id=oracle_id,
            rarity=rarity,
            set_code=set_code,
            card_type=card_type,
            mana_value_lt=mana_value_lt,
            mana_value_gt=mana_value_gt,
            mana_value_eq=mana_value_eq,
        )
        query = validator.validate_card_query(query)
        session = get_request_session(request)
        cards = await service.query_cards(session, query)
        return list(cards)

    @router.get(
        "/{card_id}",
        response_model=MtgjsonCard,
        operation_id="get_card",
        summary="Get one card by card_id.",
    )
    async def get_card_by_card_id(card_id: str, request: Request) -> MtgjsonCard:
        """
        Get one card by card_id (printing-specific). For 'other sets?' or 'all
        printings' do NOT use this; use list_cards with oracle_id (from the card's
        oracle_id field). card_id and oracle_id are different.
        """
        session = get_request_session(request)
        card = await service.query_card(session, card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Card not found")
        return card

    return router
