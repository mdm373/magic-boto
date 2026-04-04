"""ORM: ``magic_boto`` inventory tables (named collections + card quantities)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class InventoryModel(Base):
    """Named card inventory; ``name`` is stored trimmed and lowercased."""

    __tablename__ = "inventories"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list[InventoryCardModel]] = relationship(
        "InventoryCardModel",
        back_populates="inventory",
        lazy="selectin",
    )


class InventoryCardModel(Base):
    """One owned printing in an inventory (FK to ``magic_boto.cards.card_id``)."""

    __tablename__ = "inventory_cards"
    __table_args__ = {"schema": "magic_boto"}

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.inventories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("magic_boto.cards.card_id", ondelete="CASCADE"),
        primary_key=True,
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    inventory: Mapped[InventoryModel] = relationship(
        "InventoryModel",
        back_populates="items",
    )
