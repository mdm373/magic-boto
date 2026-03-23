"""MTGJSON card_subtypes junction table ORM (card_uuid, card_subtype).

`card_subtype` is free text (not enum/check constrained) because MTGJSON subtype
tokens can vary beyond our fixed standard set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .mtgjson_card import MtgjsonCardModel


class CardSubtypeModel(Base):
    """ORM model for public.card_subtypes (free-text subtype rows per card)."""

    __tablename__ = "card_subtypes"
    __table_args__ = {"schema": "public"}

    card_uuid: Mapped[str] = mapped_column(
        String,
        ForeignKey("mtgjson.cards.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    card_subtype: Mapped[str] = mapped_column(String, primary_key=True)

    card: Mapped[MtgjsonCardModel] = relationship(
        "MtgjsonCardModel",
        back_populates="card_subtypes",
    )
