"""Map MTGJSON JSON files to ``magic_boto`` SQLAlchemy ORM instances."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import ijson
from loguru import logger

from app.models import (
    CardKeywordModel,
    CardMetaModel,
    CardModel,
    CardRarity,
    CardSide,
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
    """One chunk of a set file: cards and dependent rows as ORM instances (immutable bundle)."""

    cards: Sequence[CardModel]
    card_types: Sequence[CardTypeModel]
    card_subtypes: Sequence[CardSubtypeModel]
    card_supertypes: Sequence[CardSupertypeModel]
    card_keywords: Sequence[CardKeywordModel]
    card_meta: Sequence[CardMetaModel]


class MtgJsonModelMapper:
    """Parse MTGJSON on disk and build ORM rows for ``magic_boto``."""

    def map_editions(self, path: Path) -> Sequence[EditionModel]:
        """Stream ``data[]`` from SetList.json into edition rows, excluding partial previews.

        Parsed incrementally off the file handle: reading the whole document in first cost
        ~70MB peak on an 11.6MB SetList, more than the Celery worker's entire free budget.

        Sets MTGJSON flags ``isPartialPreview`` are omitted entirely. Their files exist weeks
        before release holding only the cards spoiled so far and grow daily, so importing one
        freezes a partial snapshot: ingest only ever adds sets absent from ``editions``, so a
        set captured mid-spoiler is never revisited (FRA was stuck at 51 of 461 cards this way
        from 2026-08-27). Waiting for the flag to clear trades a short delay for not needing
        per-card reconciliation.
        """
        out: list[EditionModel] = []
        previews: list[str] = []
        with path.open("rb") as fh:
            for raw in ijson.items(fh, "data.item", use_float=True):
                item = MtgJsonSchema.SetListItem.model_validate(raw)
                code = item.code.strip()
                if not code:
                    continue
                if item.is_partial_preview:
                    previews.append(code.upper())
                    continue
                out.append(EditionModel(set_code=code.upper(), name=item.name))
        if previews:
            logger.info(
                "Skipping {} set(s) still in partial preview (MTGJSON is adding cards to these "
                "daily until release; they will import once complete): {}",
                len(previews),
                ", ".join(sorted(previews)),
            )
        return out

    def iter_set_payloads(
        self,
        *,
        path: Path,
        set_code: str,
        chunk_size: int,
    ) -> Iterator[MappedSetPayload]:
        """Yield ORM rows for at most ``chunk_size`` cards at a time.

        A generator rather than one whole-set payload so peak memory is bounded by the chunk
        instead of the set: SLD alone is 2796 cards / 13331 dependent rows. Cards come one at
        a time out of ``data.cards[]`` via ijson, so the document is never fully resident
        either. The caller is expected to insert and discard each chunk before taking the next.
        """
        cards: list[CardModel] = []
        types: list[CardTypeModel] = []
        subtypes: list[CardSubtypeModel] = []
        supertypes: list[CardSupertypeModel] = []
        keywords: list[CardKeywordModel] = []
        meta: list[CardMetaModel] = []

        def _take() -> MappedSetPayload:
            payload = MappedSetPayload(
                cards=tuple(cards),
                card_types=tuple(types),
                card_subtypes=tuple(subtypes),
                card_supertypes=tuple(supertypes),
                card_keywords=tuple(keywords),
                card_meta=tuple(meta),
            )
            for buf in (cards, types, subtypes, supertypes, keywords, meta):
                buf.clear()
            return payload

        with path.open("rb") as fh:
            for i, raw in enumerate(ijson.items(fh, "data.cards.item", use_float=True)):
                card = MtgJsonSchema.Card.model_validate(raw)
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

                sid_raw = (card.identifiers.scryfall_id or "").strip()
                if not sid_raw:
                    raise ValueError(
                        f"{path.name}: data.cards[{i}].identifiers.scryfallId missing or empty"
                    )
                sid = sid_raw.lower()

                side_token = (card.side or "").strip().lower()
                if side_token in ("", "a"):
                    card_side = CardSide.A
                elif side_token == "b":
                    card_side = CardSide.B
                else:
                    logger.warning(
                        "{}: skipping data.cards[{}] (name={!r}, uuid={!r}): side {!r} not "
                        "supported (only single-face / ``a`` / ``b`` are ingested)",
                        path.name,
                        i,
                        card.name,
                        card.uuid,
                        card.side,
                    )
                    continue

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
                        side=card_side,
                        color_identity=normalize_color_identity_string(card.color_identity),
                    )
                )

                seen_types: set[str] = set()
                for t in card.types:
                    token = t.strip().lower()
                    if not token:
                        continue
                    try:
                        type_value = CardType(token).value
                    except ValueError:
                        continue
                    if type_value in seen_types:
                        continue
                    seen_types.add(type_value)
                    types.append(CardTypeModel(card_id=card.uuid, card_type=type_value))
                seen_subtypes: set[str] = set()
                for st in card.subtypes:
                    token = st.strip().lower()
                    if not token or token in seen_subtypes:
                        continue
                    seen_subtypes.add(token)
                    subtypes.append(CardSubtypeModel(card_id=card.uuid, card_subtype=token))
                seen_supertypes: set[str] = set()
                for st in card.supertypes:
                    token = st.strip().lower()
                    if not token:
                        continue
                    try:
                        supertype_value = CardSupertype(token).value
                    except ValueError:
                        continue
                    if supertype_value in seen_supertypes:
                        continue
                    seen_supertypes.add(supertype_value)
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

                if len(cards) >= chunk_size:
                    yield _take()

        if cards:
            yield _take()

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
    """Lowercase keyword phrases from MTGJSON ``keywords`` for storage (unique per card).

    MTGJSON may repeat the same keyword; ``card_keywords`` PK is ``(card_id, card_keyword)``.
    """
    if raw is None:
        return []
    out: list[str] = []
    for item in raw:
        token = str(item).strip().lower()
        if token:
            out.append(token)
    return list(dict.fromkeys(out))
