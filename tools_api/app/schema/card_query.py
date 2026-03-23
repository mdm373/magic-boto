"""POST body for card list search: composable conditions (field + op + values + negation)."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.card_rarity import CardRarity
from app.models.card_supertype import CardSupertype
from app.models.card_type import CardType
from app.schema.descriptions import allowed_values_description


class CardQueryOp(StrEnum):
    """How each candidate compares to the column (equality, order, or pattern)."""

    EQ = "eq"
    LT = "lt"
    GT = "gt"
    LIKE = "like"


class CardQueryField(StrEnum):
    """Filterable card attributes for list search conditions.

    Numeric Fields:
    - mana_value

    All other non numeric
    """

    NAME = "name"
    CARD_ID = "card_id"
    ORACLE_ID = "oracle_id"
    RARITY = "rarity"
    SET_CODE = "set_code"
    CARD_TYPE = "card_type"
    SUBTYPE = "card_subtype"
    SUPERTYPE = "card_supertype"
    MANA_VALUE = "mana_value"


NUMERIC_QUERY_FIELDS = frozenset({CardQueryField.MANA_VALUE})
NON_NUMERIC_QUERY_FIELDS = frozenset(CardQueryField) - NUMERIC_QUERY_FIELDS
NUMERIC_OPS = frozenset({CardQueryOp.LT, CardQueryOp.GT, CardQueryOp.EQ})
NON_NUMERIC_OPS = frozenset({CardQueryOp.EQ, CardQueryOp.LIKE})


_NON_EMPTY_STR = Annotated[str, Field(min_length=1)]

candidate_value_description = (
    f" - ``rarity``, use: {allowed_values_description(CardRarity)}. "
    f" - ``card_type``: {allowed_values_description(CardType)}. "
    f" - ``card_supertype``: {allowed_values_description(CardSupertype)}. "
)


class CardQueryCondition(BaseModel):
    """One predicate: match on a field using ``value`` and/or ``values``."""

    model_config = ConfigDict(populate_by_name=True)

    field: CardQueryField = Field(
        description="Which card attribute this condition applies to.",
    )
    op: CardQueryOp = Field(
        default=CardQueryOp.EQ,
        description=("String fields support eq and ilike, numeric fields support eq, lt, and gt."),
    )
    some: bool = Field(
        default=False,
        description=(
            "for multiple values, flag as true if any of the values match, otherwise all must match"
        ),
    )
    value: str | None = Field(
        default=None,
        description=(f"Single candidate {candidate_value_description}"),
    )
    values: list[_NON_EMPTY_STR] | None = Field(
        default=None,
        description=(f"Multiple candidates. {candidate_value_description}"),
    )
    negate: bool = Field(
        default=False,
        alias="not",
        description=(
            "If true, the condition is negated (e.g. exclude rows that would otherwise match)."
        ),
    )

    @field_validator("op", mode="before")
    @classmethod
    def _default_op_eq(cls, v: object) -> object:
        if v is None:
            return CardQueryOp.EQ
        return v

    @field_validator("value", mode="after")
    @classmethod
    def _normalize_solo_value(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None

    @field_validator("values", mode="after")
    @classmethod
    def _normalize_values_entries(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for s in v:
            t = s.strip()
            if not t:
                msg = "each `values` entry must be non-empty after stripping whitespace"
                raise ValueError(msg)
            out.append(t)
        return out

    @model_validator(mode="after")
    def _validate_op_type(self) -> Self:
        if self.field in NUMERIC_QUERY_FIELDS and self.op not in NUMERIC_OPS:
            raise ValueError("numeric field does not support non numeric only operator")

        if self.field in NON_NUMERIC_QUERY_FIELDS and self.op not in NON_NUMERIC_OPS:
            raise ValueError("non numeric field does not support numeric only operator")
        return self

    @model_validator(mode="after")
    def _validate_numeric_tokens(self) -> Self:
        if self.field not in NUMERIC_QUERY_FIELDS:
            return self
        try:
            self.candidate_values_numeric()
        except ValueError as e:
            raise ValueError("numeric field requires every candidate to be an integer") from e
        return self

    @model_validator(mode="after")
    def _require_value_or_values(self) -> Self:
        has_value = self.value is not None
        has_values = self.values is not None and len(self.values) > 0
        if not has_value and not has_values:
            raise ValueError("Missing value, provide either a single `value` or a list of `values`")
        if has_value and has_values:
            raise ValueError("Provide either a single 'value' or a list of 'values', not both")
        return self

    def candidate_values_str(self) -> Sequence[str]:
        """Wire tokens from ``value`` / ``values`` (already stripped; list order preserved)."""
        if self.values is not None:
            return self.values
        if self.value is not None:
            return [self.value]
        return []

    def candidate_values_numeric(self) -> Sequence[int]:
        """Candidate values as integers."""
        return [int(value) for value in self.candidate_values_str()]


class CardQueryRequest(BaseModel):
    """Body for ``POST`` ``/mtgjson/cards``: **only** ``conditions`` plus pagination.

    Every filter—including mana (``field``: ``mana_value``, ``op``: ``lt`` / ``gt`` /
    ``eq``)—is a :class:`CardQueryCondition`. There are no extra top-level filter fields.
    """

    conditions: list[CardQueryCondition] = Field(
        min_length=1,
        description=(
            "All conditions are combined with logical AND. "
            "Use multiple conditions instead of one OR across different fields. "
            "Mana value uses ``field`` ``mana_value`` with numeric ``op`` "
            "(``eq``, ``lt``, ``gt``)."
        ),
    )
    page_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Page size (number of cards per page).",
    )
    page_number: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed).",
    )
