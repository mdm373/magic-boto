"""ORM: ``magic_boto.card_keywords`` (keyword ability line fragment)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .card_model import CardModel


class CardKeywordModel(Base):
    """Keyword ability fragment (``magic_boto.card_keywords``)."""

    __tablename__ = "card_keywords"
    __table_args__ = {"schema": "magic_boto"}

    card_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("magic_boto.cards.card_id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_keyword: Mapped[str] = mapped_column(String, primary_key=True)

    card: Mapped[CardModel] = relationship(
        "CardModel",
        back_populates="keywords",
        lazy="selectin",
    )
