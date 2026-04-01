"""Card model → Claude payload serialisation for tag tasks."""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.models.magic_boto_card import MagicBotoCardModel

# Reminder text is always parenthesised in oracle text, e.g. "(This creature can't be
# blocked except by creatures with flying or reach.)". Strip it before sending to Claude —
# it is never relevant to classification and just wastes tokens.
_REMINDER_RE = re.compile(r"\s*\([^)]+\)")


def _strip_reminder_text(text: str) -> str:
    return _REMINDER_RE.sub("", text).strip()


def card_to_dict(card: MagicBotoCardModel, reason: str | None = None) -> Mapping[str, object]:
    """Serialise a card model to the dict shape sent to Claude.

    ``reason`` is the sweep model's prior classification rationale; when provided
    it is included as ``reason_tagged`` so the audit model can reference it.
    """
    payload: dict[str, object] = {
        "oracle_id": card.oracle_id,
        "name": card.name,
        "mana_cost": card.mana_cost,
        "type": card.type_line,
        "text": _strip_reminder_text(card.oracle_text) if card.oracle_text else None,
    }
    if card.power is not None and card.toughness is not None:
        payload["power"] = card.power
        payload["toughness"] = card.toughness
    if reason:
        payload["reason_tagged"] = reason
    return payload
