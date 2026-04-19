"""MTGJSON card response and query schemas."""

from collections.abc import Callable
from typing import Any

from fastapi import Query
from fastapi_pagination import Page, Params
from fastapi_pagination.customization import CustomizedPage, UseParams
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

from app.api_schema.card_pagination_limits import CARD_CATALOG_MAX_PAGE_SIZE
from app.models.card_rarity import CardRarity
from app.models.card_side import CardSide
from app.models.card_supertype import CardSupertype
from app.models.card_type import CardType
from app.models.color_identity import ColorIdentity


class CardsPaginationParams(Params):
    """Pagination params for cards endpoints."""

    size: int = Query(
        default=100,
        ge=1,
        description=f"Page size; values above {CARD_CATALOG_MAX_PAGE_SIZE} are capped.",
    )

    @field_validator("size", mode="after")
    @classmethod
    def _clamp_size(cls, value: int) -> int:
        if value > CARD_CATALOG_MAX_PAGE_SIZE:
            return CARD_CATALOG_MAX_PAGE_SIZE
        return value


class Card(BaseModel):
    """Card row for API and MCP (subset of catalog fields).

    Optional fields may be absent by query mode. ``None`` values are omitted on serialize.
    """

    model_config = ConfigDict(title="Card")

    card_id: str = Field(..., description="Internal catalog id")
    name: str = Field(..., description="Card name")
    mana_cost: str | None = Field(None, description="Mana cost (e.g. {2}{U}{U})")
    mana_value: int | None = Field(None, description="Mana value (CMC).")
    set_code: str | None = Field(
        None,
        description="Set/edition code (e.g. M21).",
    )
    number: str | None = Field(None, description="Collector number in the set (e.g. 100, 12p)")
    scryfall_id: str = Field(
        ...,
        min_length=1,
        description="Scryfall printing id (UUID) for this printing.",
    )
    side: CardSide | None = Field(
        None,
        description="Printing side: ``a`` (primary / single-faced) or ``b`` (companion row).",
    )
    oracle_id: str | None = Field(
        None,
        description="Scryfall oracle id (card identity across printings).",
    )
    type: str | None = Field(None, description="Card type line")
    power: str | None = Field(None, description="Power text (e.g. 2, *, *+1).")
    toughness: str | None = Field(None, description="Toughness text (e.g. 2, *).")
    text: str | None = Field(None, description="Oracle / rules text.")
    card_types: list[CardType] | None = Field(
        None,
        description="Standard rulebook card types (e.g. Creature, Artifact).",
    )
    card_subtypes: list[str] | None = Field(
        None,
        description="Card subtypes (normalized lowercase, e.g. human, wizard).",
    )
    card_keywords: list[str] | None = Field(
        None,
        description="Keyword abilities (normalized lowercase, e.g. flying, trample).",
    )
    card_supertypes: list[CardSupertype] | None = Field(
        None,
        description="Card supertypes (lowercase, e.g. basic, legendary).",
    )
    color_identity: list[ColorIdentity] | None = Field(
        None,
        description="Commander color identity pips (WUBRG), WUBRG order.",
    )
    rarity: CardRarity | None = Field(None, description="Printing rarity")
    tags: list[str] | None = Field(
        None,
        description="Tags on this oracle identity (all printings).",
    )

    @model_serializer(mode="wrap")
    def _serialize_strip_none(self, handler: Callable[[Any], Any]) -> Any:
        """Drop keys whose values are ``None``."""
        data = handler(self)
        if not isinstance(data, dict):
            return data
        return {k: v for k, v in data.items() if v is not None}


class CardsListMetadata(BaseModel):
    """Metadata for cards list responses."""

    total_result_count: int = Field(..., ge=0, description="Total number of matching cards.")


class CardsListResponse(BaseModel):
    """Envelope for cards list responses."""

    metadata: CardsListMetadata
    cards: list[Card]


CardsPage = CustomizedPage[Page[Card], UseParams(CardsPaginationParams)]
