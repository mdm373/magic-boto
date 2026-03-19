"""MTGJSON card response and query schemas."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.card_rarity import CardRarity
from app.models.card_type import CardType


class CardsQuery(BaseModel):
    """Query params for listing cards (extensible)."""

    name: str | None = Field(
        default=None,
        min_length=1,
        description="Fuzzy search on card name (case-insensitive substring).",
    )
    card_id: str | None = None
    oracle_id: str | None = None
    rarity: CardRarity | None = None
    set_code: str | None = Field(
        default=None,
        min_length=1,
        description="Edition/set code (e.g. M21)",
    )
    card_type: CardType | None = Field(
        default=None,
        description="Filter by standard card type (e.g. creature, artifact).",
    )
    mana_value_lt: int | None = Field(
        default=None,
        description="Filter by mana value < this.",
    )
    mana_value_gt: int | None = Field(
        default=None,
        description="Filter by mana value > this.",
    )
    mana_value_eq: int | None = Field(
        default=None,
        description="Filter by mana value == this.",
    )

    def is_empty(self) -> bool:
        """True if no filter is set."""
        return (
            self.name is None
            and self.card_id is None
            and self.oracle_id is None
            and self.rarity is None
            and self.set_code is None
            and self.card_type is None
            and self.mana_value_lt is None
            and self.mana_value_gt is None
            and self.mana_value_eq is None
        )


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
    rarity: CardRarity = Field(..., description="Printing rarity")
