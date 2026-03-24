"""ORM mapping for public.card_meta (numeric P/T for search)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CardMetaModel(Base):
    """One row per card: optional numeric fields for search."""

    __tablename__ = "card_meta"
    __table_args__ = {"schema": "public"}

    card_uuid: Mapped[str] = mapped_column(
        String,
        ForeignKey("mtgjson.cards.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    power_number: Mapped[int | None] = mapped_column(Integer)
    toughness_number: Mapped[int | None] = mapped_column(Integer)
    collector_number: Mapped[int | None] = mapped_column(Integer)
