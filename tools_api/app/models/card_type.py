"""Standard MTG card types (Comprehensive Rules §205.2).

Values match the check constraint on ``mtgjson.card_types.card_type`` (see Alembic).
"""

from enum import StrEnum


class CardType(StrEnum):
    """Rulebook card-type line kinds"""

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
