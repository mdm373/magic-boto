"""MTGJSON cardIdentifiers table ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mtgjson_card import MtgjsonCardModel


class MtgjsonCardIdentifiersModel(Base):
    """ORM model for mtgjson.cardIdentifiers (subset of columns we use)."""

    __tablename__ = "cardIdentifiers"
    __table_args__ = {"schema": "mtgjson"}

    uuid: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("mtgjson.cards.uuid"),
        primary_key=True,
    )
    scryfall_id: Mapped[str | None] = mapped_column("scryfallId", String)

    card: Mapped[MtgjsonCardModel | None] = relationship(
        "MtgjsonCardModel",
        back_populates="identifiers",
        uselist=False,
    )
