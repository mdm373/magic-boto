"""Turn :class:`CardQueryCondition` into SQLAlchemy WHERE fragments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeAlias, cast

from sqlalchemy import and_, not_, or_
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    CardSubtypeModel,
    CardSupertypeModel,
    CardTypeModel,
    MtgjsonCardIdentifiersModel,
    MtgjsonCardModel,
)
from app.schema.card_query import (
    NUMERIC_QUERY_FIELDS,
    CardQueryCondition,
    CardQueryField,
    CardQueryOp,
)

# Card list query field -> :class:`~app.models.MtgjsonCardIdentifiersModel` column attribute.
IDENTIFIER_QUERY_FIELD_COLUMNS: Mapping[CardQueryField, str] = {
    CardQueryField.CARD_ID: "card_id",
    CardQueryField.ORACLE_ID: "oracle_id",
}
_IDENTIFIER_QUERY_FIELDS = frozenset(IDENTIFIER_QUERY_FIELD_COLUMNS.keys())

SqlPredicate: TypeAlias = ColumnElement[bool]


class _SupportsRelationshipAny(Protocol):
    """ORM collection relationship exposing ``.any(criterion)``."""

    def any(self, criterion: SqlPredicate, /) -> SqlPredicate: ...


class _StringMatchColumn(Protocol):
    """Column-like object used for string ``eq`` / ``ilike`` predicates."""

    def __eq__(self, other: object) -> SqlPredicate: ...  # type: ignore[override]
    def ilike(self, other: str, /) -> SqlPredicate: ...


class _NumericComparable(Protocol):
    """Numeric mapped column for ``lt`` / ``gt`` / ``eq`` against ``int``."""

    def __lt__(self, other: int, /) -> SqlPredicate: ...
    def __gt__(self, other: int, /) -> SqlPredicate: ...
    def __eq__(self, other: object, /) -> SqlPredicate: ...  # type: ignore[override]


# Card list query field -> :class:`~app.models.MtgjsonCardModel` column attribute name.
CARD_QUERY_FIELD_COLUMNS: Mapping[CardQueryField, str] = {
    CardQueryField.NAME: "name",
    CardQueryField.RARITY: "rarity",
    CardQueryField.SET_CODE: "set_code",
    CardQueryField.MANA_VALUE: "mana_value",
}

# ``CARD_QUERY_FIELD_COLUMNS`` entries that use ``_eq_or_ilike`` on :class:`MtgjsonCardModel`.
_MTGJSON_CARD_STRING_FIELDS = frozenset(CARD_QUERY_FIELD_COLUMNS.keys()) - NUMERIC_QUERY_FIELDS

_RelatedTextQueryEntry: TypeAlias = tuple[_SupportsRelationshipAny, _StringMatchColumn]

# Card list query field -> (card collection rel, related row text column).
RELATED_TEXT_QUERY_FIELDS_MAP: Mapping[CardQueryField, _RelatedTextQueryEntry] = {
    CardQueryField.CARD_TYPE: (MtgjsonCardModel.card_types, CardTypeModel.card_type),
    CardQueryField.SUBTYPE: (MtgjsonCardModel.card_subtypes, CardSubtypeModel.card_subtype),
    CardQueryField.SUPERTYPE: (MtgjsonCardModel.card_supertypes, CardSupertypeModel.card_supertype),
}
_RELATED_TEXT_QUERY_FIELDS = frozenset(RELATED_TEXT_QUERY_FIELDS_MAP.keys())


def _wrap(negate: bool, inner: SqlPredicate) -> SqlPredicate:
    return not_(inner) if negate else inner


def _combine_some(some: bool, parts: list[SqlPredicate]) -> SqlPredicate:
    if not parts:
        raise RuntimeError("internal: empty condition parts")
    if len(parts) == 1:
        return parts[0]
    return or_(*parts) if some else and_(*parts)


def _eq_or_ilike(column: _StringMatchColumn, token: str, op: CardQueryOp) -> SqlPredicate:
    return column == token if op == CardQueryOp.EQ else column.ilike(f"%{token}%")


def _compare_numeric(column: _NumericComparable, value: int, op: CardQueryOp) -> SqlPredicate:
    if op == CardQueryOp.LT:
        return column < value
    if op == CardQueryOp.GT:
        return column > value
    return column == value


def compile_condition(condition: CardQueryCondition) -> SqlPredicate:
    """Build one SQLAlchemy boolean expression for a single condition."""
    op = condition.op
    neg = condition.negate
    some = condition.some

    def combine(frags: list[SqlPredicate]) -> SqlPredicate:
        return _wrap(neg, _combine_some(some, frags))

    if condition.field in NUMERIC_QUERY_FIELDS:
        nums = condition.candidate_values_numeric()
        column = cast(
            _NumericComparable,
            getattr(MtgjsonCardModel, CARD_QUERY_FIELD_COLUMNS[condition.field]),
        )
        return combine([_compare_numeric(column, n, op) for n in nums])

    tokens = condition.candidate_values_str()
    if condition.field in _MTGJSON_CARD_STRING_FIELDS:
        col = cast(
            _StringMatchColumn,
            getattr(MtgjsonCardModel, CARD_QUERY_FIELD_COLUMNS[condition.field]),
        )
        return combine([_eq_or_ilike(col, t, op) for t in tokens])

    if condition.field in _IDENTIFIER_QUERY_FIELDS:
        col = cast(
            _StringMatchColumn,
            getattr(MtgjsonCardIdentifiersModel, IDENTIFIER_QUERY_FIELD_COLUMNS[condition.field]),
        )
        return combine([MtgjsonCardModel.identifiers.has(_eq_or_ilike(col, t, op)) for t in tokens])

    if condition.field in _RELATED_TEXT_QUERY_FIELDS:
        rel, col = RELATED_TEXT_QUERY_FIELDS_MAP[condition.field]
        return combine([rel.any(_eq_or_ilike(col, t, op)) for t in tokens])

    msg = f"internal: unhandled card query field {condition.field!r}"
    raise RuntimeError(msg)


def compile_conditions(conditions: list[CardQueryCondition]) -> list[SqlPredicate]:
    return [compile_condition(c) for c in conditions]
