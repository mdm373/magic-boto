"""MTGJSON card response and query schemas."""

from fastapi import Query
from fastapi_pagination import Page, Params
from fastapi_pagination.customization import CustomizedPage, UseParams
from pydantic import BaseModel, ConfigDict, Field

from app.models.card_rarity import CardRarity
from app.models.card_supertype import CardSupertype
from app.models.card_type import CardType
from app.models.color_identity import ColorIdentity


class CardsPaginationParams(Params):
    """Pagination params for cards endpoints."""

    size: int = Query(default=100, ge=1, le=1000)


class MtgjsonCard(BaseModel):
    """MTGJSON card subset for API responses (well-defined schema)."""

    model_config = ConfigDict(title="MtgjsonCard")

    card_id: str = Field(
        ..., description="Internal catalog id (primary key; unique per printing and face)."
    )
    name: str = Field(..., description="Card name")
    mana_cost: str | None = Field(None, description="Mana cost (e.g. {2}{U}{U})")
    mana_value: int = Field(..., description="Mana value (formerly CMC).")
    set_code: str = Field(..., min_length=1, description="Set/edition code (e.g. M21)")
    number: str | None = Field(None, description="Collector number in the set (e.g. 100, 12p)")
    scryfall_id: str = Field(
        ...,
        min_length=1,
        description="Scryfall printing id (UUID) for this face / printing.",
    )
    oracle_id: str = Field(
        ..., min_length=1, description="Card Definition (Cross Printing) Identifier"
    )
    type: str | None = Field(None, description="Card type line")
    power: str | None = Field(None, description="Power text (e.g. 2, *, *+1).")
    toughness: str | None = Field(None, description="Toughness text (e.g. 2, *).")
    text: str | None = Field(None, description="Oracle / rules text (MTGJSON ``text`` column).")
    card_types: list[CardType] = Field(
        default_factory=list,
        description="Standard rulebook card types (e.g. Creature, Artifact).",
    )
    card_subtypes: list[str] = Field(
        default_factory=list,
        description="Card subtypes (normalized lowercase, e.g. human, wizard).",
    )
    card_keywords: list[str] = Field(
        default_factory=list,
        description="Keyword abilities (normalized lowercase, e.g. flying, trample).",
    )
    card_supertypes: list[CardSupertype] = Field(
        default_factory=list,
        description="Card supertypes (lowercase, e.g. basic, legendary).",
    )
    color_identity: list[ColorIdentity] = Field(
        default_factory=list,
        description="Commander color identity pips (WUBRG), WUBRG order.",
    )
    rarity: CardRarity = Field(..., description="Printing rarity")
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "User-defined tags applied to this card's oracle identity "
            "(shared across all printings)."
        ),
    )


class CardsListMetadata(BaseModel):
    """Metadata for cards list responses."""

    total_result_count: int = Field(..., ge=0, description="Total number of matching cards.")


class CardsListResponse(BaseModel):
    """Envelope for cards list responses."""

    metadata: CardsListMetadata
    cards: list[MtgjsonCard]


CardsPage = CustomizedPage[Page[MtgjsonCard], UseParams(CardsPaginationParams)]
