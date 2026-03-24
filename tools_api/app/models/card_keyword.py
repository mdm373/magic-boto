"""MTGJSON card_keywords junction table ORM (card_uuid, card_keyword).

`card_keyword` is normalized lowercase text (same token rules as ``card_subtypes``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .mtgjson_card import MtgjsonCardModel


class CardKeywordModel(Base):
    """ORM model for public.card_keywords (keyword ability rows per card)."""

    __tablename__ = "card_keywords"
    __table_args__ = {"schema": "public"}

    card_uuid: Mapped[str] = mapped_column(
        String,
        ForeignKey("mtgjson.cards.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    card_keyword: Mapped[str] = mapped_column(String, primary_key=True)

    card: Mapped[MtgjsonCardModel] = relationship(
        "MtgjsonCardModel",
        back_populates="card_keywords",
    )
