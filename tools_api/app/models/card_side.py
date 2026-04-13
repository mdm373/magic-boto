"""MTGJSON printing ``side`` on ``magic_boto.cards`` (DB CHECK + ORM)."""

from enum import StrEnum


class CardSide(StrEnum):
    """Allowed ``magic_boto.cards.side`` values (same as MTGJSON ``side``)."""

    A = "a"
    B = "b"
