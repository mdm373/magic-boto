"""ORM: ``magic_boto.card_types`` (standard type line fragment)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .card_model import CardModel


class CardTypeModel(Base):
    """Standard type line fragment (``magic_boto.card_types``)."""

    __tablename__ = "card_types"
    __table_args__ = {"schema": "magic_boto"}

    card_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("magic_boto.cards.card_id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_type: Mapped[str] = mapped_column(String, primary_key=True)

    card: Mapped[CardModel] = relationship(
        "CardModel",
        back_populates="card_types",
        lazy="selectin",
    )
