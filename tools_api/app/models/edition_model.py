"""ORM: ``magic_boto.editions`` (set / edition)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .card_model import CardModel


class EditionModel(Base):
    """Set / edition row (``magic_boto.editions``)."""

    __tablename__ = "editions"
    __table_args__ = {"schema": "magic_boto"}

    set_code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)

    cards: Mapped[list["CardModel"]] = relationship(
        "CardModel",
        back_populates="edition",
        lazy="selectin",
    )
