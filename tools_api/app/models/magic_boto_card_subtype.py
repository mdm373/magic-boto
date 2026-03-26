"""ORM: ``magic_boto.card_subtypes`` (subtype line fragment)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .magic_boto_card import MagicBotoCardModel


class MagicBotoCardSubtypeModel(Base):
    """Subtype line fragment (``magic_boto.card_subtypes``)."""

    __tablename__ = "card_subtypes"
    __table_args__ = {"schema": "magic_boto"}

    card_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("magic_boto.cards.card_id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_subtype: Mapped[str] = mapped_column(String, primary_key=True)

    card: Mapped[MagicBotoCardModel] = relationship(
        "MagicBotoCardModel",
        back_populates="subtypes",
        lazy="selectin",
    )
