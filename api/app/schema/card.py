"""MTGJSON card response schema."""

from pydantic import BaseModel, Field


class MtgjsonCard(BaseModel):
    """MTGJSON card subset for API responses (well-defined schema)."""

    model_config = {"title": "MtgjsonCard"}

    name: str = Field(..., description="Card name")
    mana_cost: str | None = Field(None, description="Mana cost (e.g. {2}{U}{U})")
    set_code: str | None = Field(None, description="Set/edition code (e.g. M21)")
    scryfall_id: str | None = Field(None, description="Scryfall UUID")
    type: str | None = Field(None, description="Card type line")
    rarity: str | None = Field(None, description="Rarity")
