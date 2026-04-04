"""Map MTGJSON JSON files to ``magic_boto`` SQLAlchemy ORM instances."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.models import (
    CardKeywordModel,
    CardMetaModel,
    CardModel,
    CardRarity,
    CardSubtypeModel,
    CardSupertype,
    CardSupertypeModel,
    CardType,
    CardTypeModel,
    EditionModel,
)
from app.models.color_identity import normalize_color_identity_string

from .schema import MtgJsonSchema


@dataclass(frozen=True, slots=True)
class MappedSetPayload:
    """One set file: cards and dependent rows as ORM instances (immutable bundle)."""

    cards: Sequence[CardModel]
    card_types: Sequence[CardTypeModel]
    card_subtypes: Sequence[CardSubtypeModel]
    card_supertypes: Sequence[CardSupertypeModel]
    card_keywords: Sequence[CardKeywordModel]
    card_meta: Sequence[CardMetaModel]


class MtgJsonModelMapper:
    """Parse MTGJSON on disk and build ORM rows for ``magic_boto``."""

    def map_editions(self, path: Path) -> Sequence[EditionModel]:
        doc = MtgJsonSchema.SetListDocument.model_validate_json(path.read_text(encoding="utf-8"))
        return [
            EditionModel(set_code=item.code.strip().upper(), name=item.name)
            for item in doc.data
            if item.code.strip()
        ]

    def map_set_payload(self, *, path: Path, set_code: str) -> MappedSetPayload:
        doc = MtgJsonSchema.SetDocument.model_validate_json(path.read_text(encoding="utf-8"))
        cards: list[CardModel] = []
        types: list[CardTypeModel] = []
        subtypes: list[CardSubtypeModel] = []
        supertypes: list[CardSupertypeModel] = []
        keywords: list[CardKeywordModel] = []
        meta: list[CardMetaModel] = []

        for i, card in enumerate(doc.data.cards):
            oracle_id = card.identifiers.scryfall_oracle_id
            if not oracle_id:
                raise ValueError(
                    f"{path.name}: data.cards[{i}].identifiers.scryfallOracleId missing"
                )
            try:
                rarity_value = CardRarity(card.rarity.lower()).value
            except ValueError as err:
                allowed = ", ".join(sorted(m.value for m in CardRarity))
                raise ValueError(
                    f"{path.name}: data.cards[{i}].rarity {card.rarity!r} not allowed "
                    f"(expected one of: {allowed})"
                ) from err

            sid = (card.identifiers.scryfall_id or "").strip() or None

            cards.append(
                CardModel(
                    card_id=card.uuid,
                    oracle_id=oracle_id,
                    set_code=set_code,
                    name=card.name,
                    mana_cost=card.mana_cost,
                    collector_number=card.number,
                    type_line=card.type,
                    power=card.power,
                    toughness=card.toughness,
                    oracle_text=card.text,
                    rarity=rarity_value,
                    scryfall_id=sid,
                    color_identity=normalize_color_identity_string(card.color_identity),
                )
            )

            for t in card.types:
                token = t.strip().lower()
                if not token:
                    continue
                try:
                    type_value = CardType(token).value
                except ValueError:
                    continue
                types.append(CardTypeModel(card_id=card.uuid, card_type=type_value))
            for st in card.subtypes:
                token = st.strip().lower()
                if token:
                    subtypes.append(CardSubtypeModel(card_id=card.uuid, card_subtype=token))
            for st in card.supertypes:
                token = st.strip().lower()
                if not token:
                    continue
                try:
                    supertype_value = CardSupertype(token).value
                except ValueError:
                    continue
                supertypes.append(
                    CardSupertypeModel(
                        card_id=card.uuid,
                        card_supertype=supertype_value,
                    )
                )
            for token in _keyword_tokens(card.keywords):
                keywords.append(CardKeywordModel(card_id=card.uuid, card_keyword=token))

            meta.append(
                CardMetaModel(
                    card_id=card.uuid,
                    mana_value=self._parse_mana_value(card.mana_value),
                    power_number=self._parse_plain_integer(card.power),
                    toughness_number=self._parse_plain_integer(card.toughness),
                    collector_number=self._parse_collector_number(card.number),
                )
            )

        return MappedSetPayload(
            cards=tuple(cards),
            card_types=tuple(types),
            card_subtypes=tuple(subtypes),
            card_supertypes=tuple(supertypes),
            card_keywords=tuple(keywords),
            card_meta=tuple(meta),
        )

    @staticmethod
    def _parse_mana_value(raw: int | float | str | None) -> int:
        if raw is None:
            return 0
        if isinstance(raw, bool):
            return 0
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        s = raw.strip()
        if not s:
            return 0
        try:
            return int(float(s))
        except ValueError:
            return 0

    @staticmethod
    def _parse_plain_integer(raw: str | None) -> int | None:
        if raw is None:
            return None
        s = raw.strip()
        if not s or not re.fullmatch(r"[+-]?\d+", s):
            return None
        return int(s)

    @staticmethod
    def _parse_collector_number(raw: str | None) -> int | None:
        if raw is None:
            return None
        s = raw.strip()
        if not s:
            return None
        if s.isdigit():
            return int(s)
        m = re.match(r"^(\d+)", s)
        if m is None:
            return None
        return int(m.group(1))


def _keyword_tokens(raw: list[str] | None) -> list[str]:
    """Lowercase keyword phrases from MTGJSON ``keywords`` for storage."""
    if raw is None:
        return []
    out: list[str] = []
    for item in raw:
        token = str(item).strip().lower()
        if token:
            out.append(token)
    return out
