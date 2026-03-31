"""Card model → Claude payload serialisation for tag tasks."""

from __future__ import annotations

from collections.abc import Mapping

from app.models.magic_boto_card import MagicBotoCardModel


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
        "text": card.oracle_text,
    }
    if card.power is not None and card.toughness is not None:
        payload["power"] = card.power
        payload["toughness"] = card.toughness
    if reason:
        payload["reason_tagged"] = reason
    return payload
