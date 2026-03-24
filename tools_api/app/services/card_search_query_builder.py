"""Build SQLAlchemy predicates from :class:`CardSearchFilters`."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import exists, select
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    CardKeywordModel,
    CardMetaModel,
    CardSubtypeModel,
    CardSupertypeModel,
    MtgjsonCardIdentifiersModel,
    MtgjsonCardModel,
)
from app.schema.card_search import CardSearchFilters


class CardSearchQueryBuilder:
    """Turns :class:`CardSearchFilters` into SQLAlchemy boolean column elements (ANDed)."""

    def build_predicates(self, filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
        return [
            *_build_mana_value_filters(filters),
            *_build_name_filters(filters),
            *_build_text_like_filters(filters),
            *_build_identifier_filters(filters),
            *_build_rarity_filters(filters),
            *_build_subtype_filters(filters),
            *_build_keyword_filters(filters),
            *_build_supertype_filters(filters),
            *_build_set_code_filters(filters),
            *_build_pt_raw_filters(filters),
            *_build_pt_meta_filters(filters),
            *_build_number_filters(filters),
        ]


def _build_mana_value_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.mana_value_eq is not None:
        out.append(MtgjsonCardModel.mana_value == filters.mana_value_eq)
    if filters.mana_value_lt is not None:
        out.append(MtgjsonCardModel.mana_value < filters.mana_value_lt)
    if filters.mana_value_gt is not None:
        out.append(MtgjsonCardModel.mana_value > filters.mana_value_gt)
    return out


def _build_name_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.name_eq is not None:
        out.append(MtgjsonCardModel.name == filters.name_eq)
    if filters.name_like is not None:
        out.append(MtgjsonCardModel.name.ilike(f"%{filters.name_like}%"))
    return out


def _build_text_like_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    if filters.text_like is None:
        return ()
    return (MtgjsonCardModel.oracle_text.ilike(f"%{filters.text_like}%"),)


def _build_identifier_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.card_id is not None:
        out.append(
            MtgjsonCardModel.identifiers.has(
                MtgjsonCardIdentifiersModel.card_id == str(filters.card_id)
            )
        )
    if filters.oracle_id is not None:
        out.append(
            MtgjsonCardModel.identifiers.has(
                MtgjsonCardIdentifiersModel.oracle_id == str(filters.oracle_id)
            )
        )
    return out


def _build_rarity_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    if filters.rarity is None:
        return ()
    return (MtgjsonCardModel.rarity == filters.rarity,)


def _build_subtype_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.subtype is not None:
        out.append(
            MtgjsonCardModel.card_subtypes.any(CardSubtypeModel.card_subtype == filters.subtype)
        )
    if filters.subtype_one_of:
        out.append(
            MtgjsonCardModel.card_subtypes.any(
                CardSubtypeModel.card_subtype.in_(filters.subtype_one_of)
            )
        )
    if filters.subtype_all_of:
        out.extend(
            [
                MtgjsonCardModel.card_subtypes.any(CardSubtypeModel.card_subtype == value)
                for value in filters.subtype_all_of
            ]
        )
    return out


def _build_keyword_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.keyword is not None:
        out.append(
            MtgjsonCardModel.card_keywords.any(CardKeywordModel.card_keyword == filters.keyword)
        )
    if filters.keyword_one_of:
        out.append(
            MtgjsonCardModel.card_keywords.any(
                CardKeywordModel.card_keyword.in_(filters.keyword_one_of)
            )
        )
    if filters.keyword_all_of:
        out.extend(
            [
                MtgjsonCardModel.card_keywords.any(CardKeywordModel.card_keyword == v)
                for v in filters.keyword_all_of
            ]
        )
    return out


def _build_supertype_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    if filters.super_type is None:
        return ()
    return (
        MtgjsonCardModel.card_supertypes.any(
            CardSupertypeModel.card_supertype == filters.super_type.value
        ),
    )


def _build_set_code_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.set_code is not None:
        out.append(MtgjsonCardModel.set_code == filters.set_code)
    if filters.set_code_any_of:
        out.append(MtgjsonCardModel.set_code.in_(filters.set_code_any_of))
    return out


def _build_pt_meta_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Filter by numeric P/T in ``public.card_meta`` (plain integers only)."""
    out: list[ColumnElement[bool]] = []
    if filters.power_eq is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.power_number == filters.power_eq,
                )
            )
        )
    if filters.power_lt is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.power_number < filters.power_lt,
                )
            )
        )
    if filters.power_gt is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.power_number > filters.power_gt,
                )
            )
        )
    if filters.toughness_eq is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.toughness_number == filters.toughness_eq,
                )
            )
        )
    if filters.toughness_lt is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.toughness_number < filters.toughness_lt,
                )
            )
        )
    if filters.toughness_gt is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.toughness_number > filters.toughness_gt,
                )
            )
        )
    return out


def _build_number_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Filter by parsed collector number in ``public.card_meta``."""
    out: list[ColumnElement[bool]] = []
    if filters.number_like is not None:
        out.append(MtgjsonCardModel.number.ilike(f"%{filters.number_like}%"))
    if filters.number_eq is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.collector_number == filters.number_eq,
                )
            )
        )
    if filters.number_lt is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.collector_number < filters.number_lt,
                )
            )
        )
    if filters.number_gt is not None:
        out.append(
            exists(
                select(1)
                .select_from(CardMetaModel)
                .where(
                    CardMetaModel.card_uuid == MtgjsonCardModel.uuid,
                    CardMetaModel.collector_number > filters.number_gt,
                )
            )
        )
    return out


def _build_pt_raw_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Substring match on raw ``mtgjson.cards`` power/toughness/collector number text."""
    out: list[ColumnElement[bool]] = []
    if filters.power_like is not None:
        out.append(MtgjsonCardModel.power.ilike(f"%{filters.power_like}%"))
    if filters.toughness_like is not None:
        out.append(MtgjsonCardModel.toughness.ilike(f"%{filters.toughness_like}%"))

    return out
