"""MTGJSON card response and query schemas."""

from fastapi import Query
from fastapi_pagination import Page, Params
from fastapi_pagination.customization import CustomizedPage, UseParams
from pydantic import BaseModel, ConfigDict, Field

from app.models.card_rarity import CardRarity
from app.models.card_supertype import CardSupertype
from app.models.card_type import CardType


class CardsPaginationParams(Params):
    """Pagination params for cards endpoints."""

    size: int = Query(default=100, ge=1, le=1000)


class MtgjsonCard(BaseModel):
    """MTGJSON card subset for API responses (well-defined schema)."""

    model_config = ConfigDict(title="MtgjsonCard")

    name: str = Field(..., description="Card name")
    mana_cost: str | None = Field(None, description="Mana cost (e.g. {2}{U}{U})")
    mana_value: int = Field(..., description="Mana value (formerly CMC).")
    set_code: str = Field(..., min_length=1, description="Set/edition code (e.g. M21)")
    card_id: str = Field(..., min_length=1, description="Card Unique Printing Identifier")
    oracle_id: str = Field(
        ..., min_length=1, description="Card Definition (Cross Printing) Identifier"
    )
    type: str | None = Field(None, description="Card type line")
    card_types: list[CardType] = Field(
        default_factory=list,
        description="Standard rulebook card types (e.g. Creature, Artifact).",
    )
    card_subtypes: list[str] = Field(
        default_factory=list,
        description="Card subtypes (free text, e.g. Human, Wizard).",
    )
    card_supertypes: list[CardSupertype] = Field(
        default_factory=list,
        description="Card supertypes (e.g. Basic, Legendary).",
    )
    rarity: CardRarity = Field(..., description="Printing rarity")


class CardsListMetadata(BaseModel):
    """Metadata for cards list responses."""

    total_result_count: int = Field(..., ge=0, description="Total number of matching cards.")


class CardsListResponse(BaseModel):
    """Envelope for cards list responses."""

    metadata: CardsListMetadata
    cards: list[MtgjsonCard]


CardsPage = CustomizedPage[Page[MtgjsonCard], UseParams(CardsPaginationParams)]
