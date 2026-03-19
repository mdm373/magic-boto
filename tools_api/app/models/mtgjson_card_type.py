"""MTGJSON card_types junction table ORM (card_uuid, card_type)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .mtgjson_card import MtgjsonCardModel


class MtgjsonCardTypeModel(Base):
    """ORM model for mtgjson.card_types (standard type rows per card)."""

    __tablename__ = "card_types"
    __table_args__ = {"schema": "mtgjson"}

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
