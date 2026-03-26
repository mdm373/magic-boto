"""Pydantic models for MTGJSON wire JSON used by the fetch pipeline."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class MtgJsonSchema:
    """Namespace for MTGJSON v5 document shapes (SetList, per-set payload)."""

    class SetListItem(BaseModel):
        code: str
        name: str | None = None

    class SetListDocument(BaseModel):
        data: Sequence[MtgJsonSchema.SetListItem]

    class CardIdentifiers(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        scryfall_id: str | None = Field(default=None, alias="scryfallId")
        scryfall_oracle_id: str | None = Field(default=None, alias="scryfallOracleId")

    class Card(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        uuid: str
        name: str
        rarity: str
        identifiers: MtgJsonSchema.CardIdentifiers
        mana_cost: str | None = Field(default=None, alias="manaCost")
        number: str | None = None
        type: str | None = None
        power: str | None = None
        toughness: str | None = None
        text: str | None = None
        # MTGJSON v5 Card (Set): `keywords` is `string[]` (often omitted when empty).
        keywords: list[str] | None = None
        mana_value: int | float | str | None = Field(default=None, alias="manaValue")
        types: Sequence[str] = Field(default_factory=list)
        subtypes: Sequence[str] = Field(default_factory=list)
        supertypes: Sequence[str] = Field(default_factory=list)
        color_identity: list[str] = Field(default_factory=list, alias="colorIdentity")

    class SetData(BaseModel):
        cards: Sequence[MtgJsonSchema.Card] = Field(default_factory=list)

    class SetDocument(BaseModel):
        data: MtgJsonSchema.SetData
