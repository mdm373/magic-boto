"""Application inventory: named collection + junction to MTGJSON cards."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class InventoryModel(Base):
    """Named card inventory (e.g. personal collection)."""

    __tablename__ = "inventories"
    __table_args__ = {"schema": "public"}

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
    """One owned printing in an inventory (FK to mtgjson.cards.uuid)."""

    __tablename__ = "inventory_cards"
    __table_args__ = {"schema": "public"}

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("public.inventories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_uuid: Mapped[str] = mapped_column(
        String,
        ForeignKey("mtgjson.cards.uuid", ondelete="CASCADE"),
        primary_key=True,
    )

    # Quantity of this specific printing in the inventory.
    # Stored as a column (not duplicate rows) so each (inventory_id, card_uuid)
    # pair remains unique and indexes stay fast.
    count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
    )

    inventory: Mapped[InventoryModel] = relationship(
        "InventoryModel",
        back_populates="items",
    )
