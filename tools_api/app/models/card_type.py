"""Standard MTG card types (Comprehensive Rules §205.2).

Values align with CHECK constraints on ``magic_boto.card_types.card_type`` (see Alembic).
"""

from __future__ import annotations

from enum import StrEnum


class CardType(StrEnum):
    """Rulebook card-type line kinds."""

    artifact = "artifact"
    battle = "battle"
    conspiracy = "conspiracy"
    creature = "creature"
    dungeon = "dungeon"
    enchantment = "enchantment"
    instant = "instant"
    kindred = "kindred"
    land = "land"
    phenomenon = "phenomenon"
    plane = "plane"
    planeswalker = "planeswalker"
    scheme = "scheme"
    sorcery = "sorcery"
    vanguard = "vanguard"
