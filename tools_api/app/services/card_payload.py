"""Card model → Claude payload serialisation for tag tasks."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping, Sequence

from app.models.card_model import CardModel

# Reminder text is always parenthesised in oracle text, e.g. "(This creature can't be
# blocked except by creatures with flying or reach.)". Strip it before sending to Claude —
# it is never relevant to classification and just wastes tokens.
_REMINDER_RE = re.compile(r"\s*\([^)]+\)")
# Multiple consecutive spaces (after other normalisation).
_MULTI_SPACE_RE = re.compile(r" {2,}")


def _strip_reminder_text(text: str) -> str:
    return _REMINDER_RE.sub("", text).strip()


def _normalize_text(text: str) -> str:
    """Flatten oracle text to a single line suitable for CSV embedding.

    - Windows/classic line endings → canonical newline first.
    - Newlines (ability separators) → ' // '.
    - Tabs and other control characters → single space.
    - Collapse runs of spaces produced by the above steps.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", " // ")
    text = text.replace("\t", " ")
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def cards_to_csv(cards: Sequence[CardModel]) -> str:
    """Serialise cards to CSV with header. Row index is the identity column.

    Columns: row, mana_cost, type, text, power, toughness.
    Uses csv.writer so text fields with commas are quoted correctly.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_NONNUMERIC)
    writer.writerow(["row", "mana_cost", "type", "text", "power", "toughness"])
    for i, card in enumerate(cards):
        text = _strip_reminder_text(card.oracle_text) if card.oracle_text else ""
        if card.name and card.name in text:
            text = text.replace(card.name, "THIS CARD")
        text = _normalize_text(text)
        writer.writerow(
            [
                i,
                card.mana_cost or "",
                card.type_line or "",
                text,
                card.power if card.power is not None else "",
                card.toughness if card.toughness is not None else "",
            ]
        )
    return buf.getvalue()


def card_to_dict(card: CardModel) -> Mapping[str, object]:
    """Serialise a card model to the dict shape sent to Claude."""
    payload: dict[str, object] = {
        "name": card.name,
        "mana_cost": card.mana_cost,
        "type": card.type_line,
        "text": _strip_reminder_text(card.oracle_text) if card.oracle_text else None,
    }
    if card.power is not None and card.toughness is not None:
        payload["power"] = card.power
        payload["toughness"] = card.toughness
    return payload
