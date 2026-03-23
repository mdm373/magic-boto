"""MTG card supertypes.

Supertypes are a small fixed set (Basic, Legendary, etc.), so we model them as a
StrEnum and enforce allowed values via a CHECK constraint in migrations.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .mtgjson_card import MtgjsonCardModel


class CardSupertype(StrEnum):
    Basic = "Basic"
    Host = "Host"
    Legendary = "Legendary"
    Ongoing = "Ongoing"
    Snow = "Snow"
    World = "World"


class CardSupertypeModel(Base):
    __tablename__ = "card_supertypes"
    __table_args__ = {"schema": "public"}

    card_uuid: Mapped[str] = mapped_column(
        String,
        ForeignKey("mtgjson.cards.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    card_supertype: Mapped[str] = mapped_column(String, primary_key=True)

    card: Mapped[MtgjsonCardModel] = relationship(
        "MtgjsonCardModel",
        back_populates="card_supertypes",
    )
