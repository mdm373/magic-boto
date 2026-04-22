"""Schemas for MCP card search tool parameters."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.api_schema.card_pagination_limits import CARD_CATALOG_MAX_PAGE_SIZE
from app.models import CardRarity, CardSupertype, CardType, ColorIdentity
from app.repository.canonical import canonical_name


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
    t = canonical_name(value)
    return t if t else None


class CardSearchFilters(BaseModel):
    """Optional card search filters (AND)."""

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
        description="Exact Scryfall printing id.",
    )
    oracle_id: uuid.UUID | None = Field(
        default=None,
        title="Oracle Id",
        description="Exact Scryfall oracle id.",
    )
    inventory_name: str | None = Field(
        default=None,
        title="Inventory Name",
        description="Only cards in this inventory (canonical name).",
    )
    rarity: CardRarity | None = Field(
        default=None,
        title="Rarity",
        description="Exact rarity match.",
    )
    subtype: str | None = Field(
        default=None,
        title="Subtype",
        description="Require this subtype token.",
    )
    subtype_one_of: list[str] | None = Field(
        default=None,
        title="Subtype (One Of)",
        description="Require at least one of these subtype tokens (OR).",
    )
    subtype_all_of: list[str] | None = Field(
        default=None,
        title="Subtype (All Of)",
        description="Require all of these subtype tokens (AND).",
    )
    keyword: str | None = Field(
        default=None,
        title="Keyword",
        description="Require this keyword ability token.",
    )
    keyword_one_of: list[str] | None = Field(
        default=None,
        title="Keyword (One Of)",
        description="Require at least one of these keyword tokens (OR).",
    )
    keyword_all_of: list[str] | None = Field(
        default=None,
        title="Keyword (All Of)",
        description="Require all of these keyword tokens (AND).",
    )
    tag: str | None = Field(
        default=None,
        title="Tag",
        description="Require this user tag on the oracle identity.",
    )
    tag_one_of: list[str] | None = Field(
        default=None,
        title="Tag (One Of)",
        description="Require at least one of these tags (OR).",
    )
    tag_all_of: list[str] | None = Field(
        default=None,
        title="Tag (All Of)",
        description="Require all of these tags (AND).",
    )
    super_type: CardSupertype | None = Field(
        default=None,
        title="Super Type",
        description="Require a single supertype (case-insensitive, e.g. 'Legendary', 'Basic').",
    )
    set_code: str | None = Field(
        default=None,
        title="Set Code",
        description="Require this edition set code.",
    )
    set_code_any_of: list[str] | None = Field(
        default=None,
        title="Set Code (Any Of)",
        description="Set code is one of these (OR).",
    )
    power_eq: int | None = Field(
        default=None,
        ge=0,
        title="Power (Equal)",
        description="Integer power equal to this (non-numeric powers do not match).",
    )
    power_lt: int | None = Field(
        default=None,
        ge=0,
        title="Power (Less Than)",
        description="Integer power strictly less than this value.",
    )
    power_gt: int | None = Field(
        default=None,
        ge=0,
        title="Power (Greater Than)",
        description="Integer power strictly greater than this value.",
    )
    toughness_eq: int | None = Field(
        default=None,
        ge=0,
        title="Toughness (Equal)",
        description="Integer toughness equal to this (non-numeric toughness does not match).",
    )
    toughness_lt: int | None = Field(
        default=None,
        ge=0,
        title="Toughness (Less Than)",
        description="Integer toughness strictly less than this value.",
    )
    toughness_gt: int | None = Field(
        default=None,
        ge=0,
        title="Toughness (Greater Than)",
        description="Integer toughness strictly greater than this value.",
    )
    power_like: str | None = Field(
        default=None,
        title="Power (Like)",
        description="Case-insensitive substring on printed power text.",
    )
    toughness_like: str | None = Field(
        default=None,
        title="Toughness (Like)",
        description="Case-insensitive substring on printed toughness text.",
    )
    text_like: str | None = Field(
        default=None,
        title="Text (Like)",
        description="Case-insensitive substring on oracle / rules text.",
    )
    number_eq: int | None = Field(
        default=None,
        ge=0,
        title="Collector Number (Equal)",
        description="Numeric collector number equal to this (unparsed numbers do not match).",
    )
    number_lt: int | None = Field(
        default=None,
        ge=0,
        title="Collector Number (Less Than)",
        description="Numeric collector number strictly less than this value.",
    )
    number_gt: int | None = Field(
        default=None,
        ge=0,
        title="Collector Number (Greater Than)",
        description="Numeric collector number strictly greater than this value.",
    )
    number_like: str | None = Field(
        default=None,
        title="Collector Number (Like)",
        description="Case-insensitive substring on collector number text.",
    )
    color_identity: ColorIdentity | None = Field(
        default=None,
        title="Color Identity",
        description="Card's color identity contains this pip (single-pip presence filter).",
    )
    color_identity_one_of: list[ColorIdentity] | None = Field(
        default=None,
        title="Color Identity (One Of)",
        description="Color identity includes at least one of these pips.",
    )
    color_identity_all_of: list[ColorIdentity] | None = Field(
        default=None,
        title="Color Identity (All Of)",
        description="Card's color identity is a superset of these pips.",
    )
    color_identity_only_of: list[ColorIdentity] | None = Field(
        default=None,
        title="Color Identity (Only Of)",
        description="Card's color identity is a subset of these pips and colorless.",
    )
    card_type: CardType | None = Field(
        default=None,
        title="Card Type",
        description="Printing has this rulebook card type (case-insensitive, e.g. 'Creature').",
    )
    card_type_one_of: list[CardType] | None = Field(
        default=None,
        title="Card Type (One Of)",
        description="Printing has at least one of these card types (OR; case-insensitive).",
    )
    card_type_all_of: list[CardType] | None = Field(
        default=None,
        title="Card Type (All Of)",
        description="Printing has all of these card types (AND; case-insensitive).",
    )

    @field_validator("card_type", "super_type", mode="before")
    @classmethod
    def _lowercase_enum_field(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("card_type_one_of", "card_type_all_of", mode="before")
    @classmethod
    def _lowercase_enum_list_field(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [v.strip().lower() if isinstance(v, str) else v for v in value]
        return value

    @field_validator("subtype", "keyword", "tag", mode="after")
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
        "tag_one_of",
        "tag_all_of",
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
        "color_identity_only_of",
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

    page_size: int = Field(
        default=100,
        ge=1,
        title="Page Size",
        description=f"Rows per page; values above {CARD_CATALOG_MAX_PAGE_SIZE} are capped.",
    )
    page_number: int = Field(default=1, ge=1, title="Page Number")

    @field_validator("page_size", mode="after")
    @classmethod
    def _clamp_page_size(cls, value: int) -> int:
        if value > CARD_CATALOG_MAX_PAGE_SIZE:
            return CARD_CATALOG_MAX_PAGE_SIZE
        return value


class CardSearchFlags(BaseModel):
    """Non-filter search behavior toggles (mostly MCP-facing)."""

    verbose: bool = Field(
        default=False,
        title="Verbose",
        description="Return full card fields; default is a minimal card row.",
    )
    distinct_oracle: bool = Field(
        default=False,
        title="Distinct Oracle",
        description="At most one printing per oracle id (stable order for paging the catalog).",
    )


class CardSearchQuery(BaseModel):
    """Shared card search request body for HTTP and MCP."""

    filters: CardSearchFilters = Field(default_factory=CardSearchFilters)
    pagination: CardSearchPagination = Field(default_factory=CardSearchPagination)
    flags: CardSearchFlags = Field(default_factory=CardSearchFlags)
