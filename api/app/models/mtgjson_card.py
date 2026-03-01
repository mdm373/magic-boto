"""MTGJSON cards table ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mtgjson_identifiers import MtgjsonCardIdentifiersModel


class MtgjsonCardModel(Base):
    """ORM model for mtgjson.cards (subset of columns we use)."""

    __tablename__ = "cards"
    __table_args__ = {"schema": "mtgjson"}

    uuid: Mapped[str | None] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    mana_cost: Mapped[str | None] = mapped_column("manaCost", String)
    set_code: Mapped[str | None] = mapped_column("setCode", String)
    type: Mapped[str | None] = mapped_column(String)
    rarity: Mapped[str | None] = mapped_column(String)

    identifiers: Mapped[MtgjsonCardIdentifiersModel | None] = relationship(
        "MtgjsonCardIdentifiersModel",
        back_populates="card",
        uselist=False,
        lazy="joined",
    )
