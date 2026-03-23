"""MTGJSON cards table ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .card_rarity import CardRarity
from .text_enum import text_enum

if TYPE_CHECKING:
    from .card_subtype import CardSubtypeModel
    from .card_supertype import CardSupertypeModel
    from .card_type import CardTypeModel
    from .mtgjson_edition import MtgjsonEditionModel
    from .mtgjson_identifiers import MtgjsonCardIdentifiersModel


class MtgjsonCardModel(Base):
    """ORM model for mtgjson.cards (subset of columns we use)."""

    __tablename__ = "cards"
    __table_args__ = {"schema": "mtgjson"}

    uuid: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    mana_cost: Mapped[str | None] = mapped_column("manaCost", String)
    mana_value: Mapped[float] = mapped_column("manaValue", Float, nullable=False)
    set_code: Mapped[str | None] = mapped_column(
        "setCode",
        String,
        ForeignKey("mtgjson.sets.code"),
    )
    type: Mapped[str | None] = mapped_column(String)
    rarity: Mapped[CardRarity] = mapped_column("rarity", text_enum(CardRarity), nullable=False)

    identifiers: Mapped[MtgjsonCardIdentifiersModel | None] = relationship(
        "MtgjsonCardIdentifiersModel",
        back_populates="card",
        uselist=False,
        lazy="joined",
    )
    edition: Mapped[MtgjsonEditionModel | None] = relationship(
        "MtgjsonEditionModel",
        lazy="select",
        viewonly=True,
    )
    card_types: Mapped[list[CardTypeModel]] = relationship(
        "CardTypeModel",
        back_populates="card",
        lazy="selectin",
        order_by="CardTypeModel.card_type",
    )

    card_subtypes: Mapped[list[CardSubtypeModel]] = relationship(
        "CardSubtypeModel",
        back_populates="card",
        lazy="selectin",
        order_by="CardSubtypeModel.card_subtype",
    )

    card_supertypes: Mapped[list[CardSupertypeModel]] = relationship(
        "CardSupertypeModel",
        back_populates="card",
        lazy="selectin",
        order_by="CardSupertypeModel.card_supertype",
    )
