"""Printing rarity values stored on mtgjson.cards.rarity (DB CHECK + ORM)."""

from enum import StrEnum


class CardRarity(StrEnum):
    """Allowed card rarity values"""

    BONUS = "bonus"
    COMMON = "common"
    MYTHIC = "mythic"
    RARE = "rare"
    SPECIAL = "special"
    UNCOMMON = "uncommon"
