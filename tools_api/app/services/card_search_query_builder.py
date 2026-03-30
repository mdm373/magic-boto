"""Build SQLAlchemy predicates from :class:`CardSearchFilters`."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import exists, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    MagicBotoCardKeywordModel,
    MagicBotoCardMetaModel,
    MagicBotoCardModel,
    MagicBotoCardSubtypeModel,
    MagicBotoCardSupertypeModel,
    MagicBotoCardTagModel,
    MagicBotoCardTypeModel,
    MagicBotoInventoryCardModel,
    MagicBotoInventoryModel,
    MagicBotoTagModel,
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
            *_build_inventory_filters(filters),
            *_build_rarity_filters(filters),
            *_build_subtype_filters(filters),
            *_build_keyword_filters(filters),
            *_build_supertype_filters(filters),
            *_build_set_code_filters(filters),
            *_build_pt_raw_filters(filters),
            *_build_pt_meta_filters(filters),
            *_build_number_filters(filters),
            *_build_color_identity_filters(filters),
            *_build_card_type_filters(filters),
            *_build_tag_filters(filters),
        ]


def _build_mana_value_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.mana_value_eq is not None:
        out.append(_meta_mana_eq(filters.mana_value_eq))
    if filters.mana_value_lt is not None:
        out.append(_meta_mana_lt(filters.mana_value_lt))
    if filters.mana_value_gt is not None:
        out.append(_meta_mana_gt(filters.mana_value_gt))
    return out


def _meta_mana_eq(val: int) -> ColumnElement[bool]:
    return exists(
        select(1)
        .select_from(MagicBotoCardMetaModel)
        .where(
            MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
            MagicBotoCardMetaModel.mana_value == val,
        )
    )


def _meta_mana_lt(val: int) -> ColumnElement[bool]:
    return exists(
        select(1)
        .select_from(MagicBotoCardMetaModel)
        .where(
            MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
            MagicBotoCardMetaModel.mana_value < val,
        )
    )


def _meta_mana_gt(val: int) -> ColumnElement[bool]:
    return exists(
        select(1)
        .select_from(MagicBotoCardMetaModel)
        .where(
            MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
            MagicBotoCardMetaModel.mana_value > val,
        )
    )


def _build_name_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.name_eq is not None:
        out.append(MagicBotoCardModel.name == filters.name_eq)
    if filters.name_like is not None:
        out.append(MagicBotoCardModel.name.ilike(f"%{filters.name_like}%"))
    return out


def _build_text_like_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    if filters.text_like is None:
        return ()
    return (MagicBotoCardModel.oracle_text.ilike(f"%{filters.text_like}%"),)


def _build_identifier_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.scryfall_id is not None:
        out.append(MagicBotoCardModel.scryfall_id == str(filters.scryfall_id))
    if filters.oracle_id is not None:
        out.append(MagicBotoCardModel.oracle_id == str(filters.oracle_id))
    return out


def _build_inventory_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    if filters.inventory_name is None:
        return ()
    return (
        exists(
            select(1)
            .select_from(MagicBotoInventoryCardModel)
            .join(
                MagicBotoInventoryModel,
                MagicBotoInventoryCardModel.inventory_id == MagicBotoInventoryModel.id,
            )
            .where(
                MagicBotoInventoryCardModel.card_id == MagicBotoCardModel.card_id,
                MagicBotoInventoryModel.name == filters.inventory_name,
            )
        ),
    )


def _build_rarity_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    if filters.rarity is None:
        return ()
    return (MagicBotoCardModel.rarity == filters.rarity,)


def _build_subtype_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.subtype is not None:
        out.append(
            MagicBotoCardModel.subtypes.any(
                MagicBotoCardSubtypeModel.card_subtype == filters.subtype
            )
        )
    if filters.subtype_one_of:
        out.append(
            MagicBotoCardModel.subtypes.any(
                MagicBotoCardSubtypeModel.card_subtype.in_(filters.subtype_one_of)
            )
        )
    if filters.subtype_all_of:
        out.extend(
            [
                MagicBotoCardModel.subtypes.any(MagicBotoCardSubtypeModel.card_subtype == value)
                for value in filters.subtype_all_of
            ]
        )
    return out


def _build_keyword_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.keyword is not None:
        out.append(
            MagicBotoCardModel.keywords.any(
                MagicBotoCardKeywordModel.card_keyword == filters.keyword
            )
        )
    if filters.keyword_one_of:
        out.append(
            MagicBotoCardModel.keywords.any(
                MagicBotoCardKeywordModel.card_keyword.in_(filters.keyword_one_of)
            )
        )
    if filters.keyword_all_of:
        out.extend(
            [
                MagicBotoCardModel.keywords.any(MagicBotoCardKeywordModel.card_keyword == v)
                for v in filters.keyword_all_of
            ]
        )
    return out


def _build_supertype_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    if filters.super_type is None:
        return ()
    return (
        MagicBotoCardModel.supertypes.any(
            MagicBotoCardSupertypeModel.card_supertype == filters.super_type.value
        ),
    )


def _build_set_code_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.set_code is not None:
        out.append(MagicBotoCardModel.set_code == filters.set_code)
    if filters.set_code_any_of:
        out.append(MagicBotoCardModel.set_code.in_(filters.set_code_any_of))
    return out


def _build_pt_meta_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Filter by numeric P/T in ``magic_boto.card_meta`` (plain integers only)."""
    out: list[ColumnElement[bool]] = []
    if filters.power_eq is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.power_number == filters.power_eq,
                )
            )
        )
    if filters.power_lt is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.power_number < filters.power_lt,
                )
            )
        )
    if filters.power_gt is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.power_number > filters.power_gt,
                )
            )
        )
    if filters.toughness_eq is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.toughness_number == filters.toughness_eq,
                )
            )
        )
    if filters.toughness_lt is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.toughness_number < filters.toughness_lt,
                )
            )
        )
    if filters.toughness_gt is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.toughness_number > filters.toughness_gt,
                )
            )
        )
    return out


def _build_number_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Filter by parsed collector number in ``magic_boto.card_meta``."""
    out: list[ColumnElement[bool]] = []
    if filters.number_like is not None:
        out.append(MagicBotoCardModel.collector_number.ilike(f"%{filters.number_like}%"))
    if filters.number_eq is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.collector_number == filters.number_eq,
                )
            )
        )
    if filters.number_lt is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.collector_number < filters.number_lt,
                )
            )
        )
    if filters.number_gt is not None:
        out.append(
            exists(
                select(1)
                .select_from(MagicBotoCardMetaModel)
                .where(
                    MagicBotoCardMetaModel.card_id == MagicBotoCardModel.card_id,
                    MagicBotoCardMetaModel.collector_number > filters.number_gt,
                )
            )
        )
    return out


def _build_pt_raw_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Substring match on raw ``magic_boto.cards`` power/toughness text."""
    out: list[ColumnElement[bool]] = []
    if filters.power_like is not None:
        out.append(MagicBotoCardModel.power.ilike(f"%{filters.power_like}%"))
    if filters.toughness_like is not None:
        out.append(MagicBotoCardModel.toughness.ilike(f"%{filters.toughness_like}%"))

    return out


def _build_color_identity_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Filter by canonical ``magic_boto.cards.color_identity`` string (WUBRG pips)."""
    out: list[ColumnElement[bool]] = []
    if filters.color_identity is not None:
        out.append(MagicBotoCardModel.color_identity.like(f"%{filters.color_identity.value}%"))
    if filters.color_identity_one_of:
        out.append(
            or_(
                *[
                    MagicBotoCardModel.color_identity.like(f"%{c.value}%")
                    for c in filters.color_identity_one_of
                ]
            )
        )
    if filters.color_identity_all_of:
        out.extend(
            MagicBotoCardModel.color_identity.like(f"%{c.value}%")
            for c in filters.color_identity_all_of
        )
    return out


def _build_card_type_filters(
    filters: CardSearchFilters,
) -> Sequence[ColumnElement[bool]]:
    """Filter via ``magic_boto.card_types`` junction."""
    out: list[ColumnElement[bool]] = []
    if filters.card_type is not None:
        out.append(
            MagicBotoCardModel.card_types.any(
                MagicBotoCardTypeModel.card_type == filters.card_type.value
            )
        )
    if filters.card_type_one_of:
        values = [ct.value for ct in filters.card_type_one_of]
        out.append(MagicBotoCardModel.card_types.any(MagicBotoCardTypeModel.card_type.in_(values)))
    if filters.card_type_all_of:
        for ct in filters.card_type_all_of:
            out.append(
                MagicBotoCardModel.card_types.any(MagicBotoCardTypeModel.card_type == ct.value)
            )
    return out


def _tag_subquery(tag_name: str) -> ColumnElement[bool]:
    """True when the card's oracle_id has the named tag."""
    return exists(
        select(1)
        .select_from(MagicBotoCardTagModel)
        .join(MagicBotoTagModel, MagicBotoCardTagModel.tag_id == MagicBotoTagModel.id)
        .where(
            MagicBotoCardTagModel.oracle_id == MagicBotoCardModel.oracle_id,
            MagicBotoTagModel.name == tag_name,
        )
    )


def _build_tag_filters(filters: CardSearchFilters) -> Sequence[ColumnElement[bool]]:
    out: list[ColumnElement[bool]] = []
    if filters.tag is not None:
        out.append(_tag_subquery(filters.tag))
    if filters.tag_one_of:
        out.append(or_(*[_tag_subquery(t) for t in filters.tag_one_of]))
    if filters.tag_all_of:
        out.extend(_tag_subquery(t) for t in filters.tag_all_of)
    return out
