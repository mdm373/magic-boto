"""Standard MTG card types (Comprehensive Rules §205.2).

Values match the check constraint on ``mtgjson.card_types.card_type`` (see Alembic).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .mtgjson_card import MtgjsonCardModel


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

    """ORM model for mtgjson.card_types (standard type rows per card)."""


class CardTypeModel(Base):
    __tablename__ = "card_types"
    __table_args__ = {"schema": "public"}

    card_uuid: Mapped[str] = mapped_column(
        String,
        ForeignKey("mtgjson.cards.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    card_type: Mapped[str] = mapped_column(String, primary_key=True)

    card: Mapped[MtgjsonCardModel] = relationship(
        "MtgjsonCardModel",
        back_populates="card_types",
    )
