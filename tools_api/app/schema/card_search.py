"""Schemas for MCP card search tool parameters."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.inventory.names import canonical_inventory_name
from app.models import CardRarity, CardSupertype, CardType, ColorIdentity


def _normalize_optional_search_token(value: str | None) -> str | None:
    """Trim + lowercase; empty after trim becomes ``None`` (no filter)."""
    if value is None:
        return None
    t = value.strip().lower()
    return t if t else None


def _normalize_search_token_list(value: list[str] | None) -> list[str] | None:
    """Trim + lowercase each item; drop empties; ``None`` if nothing left."""
    if value is None:
        return None
    out: list[str] = []
    for item in value:
        t = item.strip().lower()
        if t:
            out.append(t)
    return out if out else None


def _normalize_optional_set_code(value: str | None) -> str | None:
    """Trim + uppercase to match ``mtgjson.cards.setCode`` storage; empty becomes ``None``."""
    if value is None:
        return None
    t = value.strip().upper()
    return t if t else None


def _normalize_set_code_list(value: list[str] | None) -> list[str] | None:
    """Trim + uppercase each item; drop empties; ``None`` if nothing left."""
    if value is None:
        return None
    out: list[str] = []
    for item in value:
        t = item.strip().upper()
        if t:
            out.append(t)
    return out if out else None


def _normalize_optional_like(value: str | None) -> str | None:
    """Trim; empty after trim becomes ``None`` (no filter)."""
    if value is None:
        return None
    t = value.strip()
    return t if t else None


def _normalize_inventory_name(value: str | None) -> str | None:
    """Same canonical form as stored ``inventories.name``; empty becomes ``None``."""
    if value is None:
        return None
    t = canonical_inventory_name(value)
    return t if t else None


class CardSearchFilters(BaseModel):
    """Optional filters for card search. Populated fields are ANDed together."""

    mana_value_eq: int | None = Field(
        default=None,
        title="Mana Value (Equal)",
        description="Exact mana value match.",
    )
    mana_value_lt: int | None = Field(
        default=None,
        title="Mana Value (Less Than)",
        description="Mana value strictly less than.",
    )
    mana_value_gt: int | None = Field(
        default=None,
        title="Mana Value (Greater Than)",
        description="Mana value strictly greater than.",
    )
    name_eq: str | None = Field(
        default=None,
        title="Name (Equal)",
        description="Exact card name match.",
    )
    name_like: str | None = Field(
        default=None,
        title="Name (Like)",
        description="Case-insensitive partial name match.",
    )
    scryfall_id: uuid.UUID | None = Field(
        default=None,
        title="Scryfall Id",
        description="Exact match on Scryfall printing id (same UUID as in card responses).",
    )
    oracle_id: uuid.UUID | None = Field(
        default=None,
        title="Oracle Id",
        description="Cross-printing Scryfall oracle id.",
    )
    inventory_name: str | None = Field(
        default=None,
        title="Inventory Name",
        description=(
            "Limit results to cards in the inventory with this name (trimmed, lowercase)."
        ),
    )
    rarity: CardRarity | None = Field(
        default=None,
        title="Rarity",
        description="Exact rarity match.",
    )
    subtype: str | None = Field(
        default=None,
        title="Subtype",
        description="Require a single subtype (trimmed, lowercased).",
    )
    subtype_one_of: list[str] | None = Field(
        default=None,
        title="Subtype (One Of)",
        description="Require at least one subtype from this list (each trimmed, lowercased).",
    )
    subtype_all_of: list[str] | None = Field(
        default=None,
        title="Subtype (All Of)",
        description="Require all listed subtypes (each trimmed, lowercased).",
    )
    keyword: str | None = Field(
        default=None,
        title="Keyword",
        description=("Require a single keyword ability (trimmed, lowercased)."),
    )
    keyword_one_of: list[str] | None = Field(
        default=None,
        title="Keyword (One Of)",
        description="Require at least one keyword from this list (OR; each trimmed, lowercased).",
    )
    keyword_all_of: list[str] | None = Field(
        default=None,
        title="Keyword (All Of)",
        description="Require all listed keywords (AND; each trimmed, lowercased).",
    )
    super_type: CardSupertype | None = Field(
        default=None,
        title="Super Type",
        description="Require a single supertype.",
    )
    set_code: str | None = Field(
        default=None,
        title="Set Code",
        description="Require a single set code (trimmed, uppercased; matches DB ``setCode``).",
    )
    set_code_any_of: list[str] | None = Field(
        default=None,
        title="Set Code (Any Of)",
        description="Match if set code is any of these (OR; each trimmed, uppercased).",
    )
    power_eq: int | None = Field(
        default=None,
        ge=0,
        title="Power (Equal)",
        description=(
            "Numeric power from ``public.card_meta`` (plain integer P/T only). "
            "Cards without a numeric power have no match."
        ),
    )
    power_lt: int | None = Field(
        default=None,
        ge=0,
        title="Power (Less Than)",
        description="``card_meta.power_number`` strictly less than this value.",
    )
    power_gt: int | None = Field(
        default=None,
        ge=0,
        title="Power (Greater Than)",
        description="``card_meta.power_number`` strictly greater than this value.",
    )
    toughness_eq: int | None = Field(
        default=None,
        ge=0,
        title="Toughness (Equal)",
        description=(
            "Numeric toughness from ``public.card_meta`` (plain integer P/T only). "
            "Cards without a numeric toughness have no match."
        ),
    )
    toughness_lt: int | None = Field(
        default=None,
        ge=0,
        title="Toughness (Less Than)",
        description="``card_meta.toughness_number`` strictly less than this value.",
    )
    toughness_gt: int | None = Field(
        default=None,
        ge=0,
        title="Toughness (Greater Than)",
        description="``card_meta.toughness_number`` strictly greater than this value.",
    )
    power_like: str | None = Field(
        default=None,
        title="Power (Like)",
        description="Case-insensitive substring match on raw ``mtgjson.cards.power`` text.",
    )
    toughness_like: str | None = Field(
        default=None,
        title="Toughness (Like)",
        description="Case-insensitive substring match on raw ``mtgjson.cards.toughness`` text.",
    )
    text_like: str | None = Field(
        default=None,
        title="Text (Like)",
        description=(
            "Case-insensitive substring match on oracle / rules text (``mtgjson.cards.text``)."
        ),
    )
    number_eq: int | None = Field(
        default=None,
        ge=0,
        title="Collector Number (Equal)",
        description=(
            "Numeric collector number from ``public.card_meta.collector_number`` "
            "(parsed from ``mtgjson.cards.number``). No match if unset in meta."
        ),
    )
    number_lt: int | None = Field(
        default=None,
        ge=0,
        title="Collector Number (Less Than)",
        description="``card_meta.collector_number`` strictly less than this value.",
    )
    number_gt: int | None = Field(
        default=None,
        ge=0,
        title="Collector Number (Greater Than)",
        description="``card_meta.collector_number`` strictly greater than this value.",
    )
    number_like: str | None = Field(
        default=None,
        title="Collector Number (Like)",
        description="Case-insensitive substring match on raw ``mtgjson.cards.number`` text.",
    )
    color_identity: ColorIdentity | None = Field(
        default=None,
        title="Color Identity",
        description="Card's color identity contains this pip (single-pip presence filter).",
    )
    color_identity_one_of: list[ColorIdentity] | None = Field(
        default=None,
        title="Color Identity (One Of)",
        description=(
            "Card's color identity includes at least one of these pips (OR). "
            "Stored as WUBRG-ordered string; matched by pip presence."
        ),
    )
    color_identity_all_of: list[ColorIdentity] | None = Field(
        default=None,
        title="Color Identity (All Of)",
        description="Card's color identity includes every listed pip (AND).",
    )
    card_type: CardType | None = Field(
        default=None,
        title="Card Type",
        description="Printing has this rulebook card type (single-type presence filter).",
    )
    card_type_one_of: list[CardType] | None = Field(
        default=None,
        title="Card Type (One Of)",
        description="Printing has at least one of these rulebook card types (OR).",
    )
    card_type_all_of: list[CardType] | None = Field(
        default=None,
        title="Card Type (All Of)",
        description="Printing has all of these card types (AND).",
    )

    @field_validator("subtype", "keyword", mode="after")
    @classmethod
    def _normalize_optional_tokens(cls, value: str | None) -> str | None:
        return _normalize_optional_search_token(value)

    @field_validator("set_code", mode="after")
    @classmethod
    def _normalize_set_code_field(cls, value: str | None) -> str | None:
        return _normalize_optional_set_code(value)

    @field_validator(
        "subtype_one_of",
        "subtype_all_of",
        "keyword_one_of",
        "keyword_all_of",
        mode="after",
    )
    @classmethod
    def _normalize_token_lists(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_search_token_list(value)

    @field_validator("set_code_any_of", mode="after")
    @classmethod
    def _normalize_set_code_any_of_field(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_set_code_list(value)

    @field_validator("power_like", "toughness_like", "text_like", "number_like", mode="after")
    @classmethod
    def _normalize_optional_like_fields(cls, value: str | None) -> str | None:
        return _normalize_optional_like(value)

    @field_validator("inventory_name", mode="after")
    @classmethod
    def _normalize_inventory_name_field(cls, value: str | None) -> str | None:
        return _normalize_inventory_name(value)

    @field_validator(
        "color_identity_one_of",
        "color_identity_all_of",
        "card_type_one_of",
        "card_type_all_of",
        mode="after",
    )
    @classmethod
    def _empty_list_means_no_filter(cls, value: list[Any] | None) -> list[Any] | None:
        if value is None or len(value) == 0:
            return None
        return value


class CardSearchPagination(BaseModel):
    """Pagination settings for card search."""

    page_size: int = Field(default=100, ge=1, le=1000, title="Page Size")
    page_number: int = Field(default=1, ge=1, title="Page Number")


class CardSearchQuery(BaseModel):
    """Shared card search request body for HTTP and MCP."""

    filters: CardSearchFilters = Field(default_factory=CardSearchFilters)
    pagination: CardSearchPagination = Field(default_factory=CardSearchPagination)
