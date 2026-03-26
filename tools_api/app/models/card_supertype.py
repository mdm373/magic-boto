"""MTG card supertypes.

Supertypes are a small fixed set (basic, legendary, etc.), modeled as a StrEnum and
enforced via CHECK constraints in migrations.
"""

from __future__ import annotations

from enum import StrEnum


class CardSupertype(StrEnum):
    basic = "basic"
    host = "host"
    legendary = "legendary"
    ongoing = "ongoing"
    snow = "snow"
    world = "world"
