"""ORM: ``magic_boto.card_meta`` (numeric fields for search)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .magic_boto_card import MagicBotoCardModel


class MagicBotoCardMetaModel(Base):
    """Numeric fields for search (``magic_boto.card_meta``)."""

    __tablename__ = "card_meta"
    __table_args__ = {"schema": "magic_boto"}

    card_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("magic_boto.cards.card_id", ondelete="CASCADE"),
        primary_key=True,
    )
    mana_value: Mapped[int] = mapped_column(Integer, nullable=False)
    power_number: Mapped[int | None] = mapped_column(Integer)
    toughness_number: Mapped[int | None] = mapped_column(Integer)
    collector_number: Mapped[int | None] = mapped_column(Integer)

    card: Mapped[MagicBotoCardModel] = relationship(
        "MagicBotoCardModel",
        back_populates="meta",
        lazy="selectin",
    )
