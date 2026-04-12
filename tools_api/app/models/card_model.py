"""ORM: ``magic_boto.cards`` (one printing in the catalog)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .edition_model import EditionModel

if TYPE_CHECKING:
    from .card_keyword_model import CardKeywordModel
    from .card_meta_model import CardMetaModel
    from .card_subtype_model import CardSubtypeModel
    from .card_supertype_model import CardSupertypeModel
    from .card_tag_model import CardTagModel
    from .card_type_model import CardTypeModel


class CardModel(Base):
    """One printing in the catalog (``magic_boto.cards``)."""

    __tablename__ = "cards"
    __table_args__ = {"schema": "magic_boto"}

    card_id: Mapped[str] = mapped_column(String, primary_key=True)
    oracle_id: Mapped[str] = mapped_column(String, nullable=False)
    set_code: Mapped[str] = mapped_column(
        String,
        ForeignKey("magic_boto.editions.set_code", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    mana_cost: Mapped[str | None] = mapped_column(String)
    collector_number: Mapped[str | None] = mapped_column(String)
    type_line: Mapped[str | None] = mapped_column(String)
    power: Mapped[str | None] = mapped_column(String)
    toughness: Mapped[str | None] = mapped_column(String)
    oracle_text: Mapped[str | None] = mapped_column(String)
    rarity: Mapped[str] = mapped_column(String, nullable=False)
    scryfall_id: Mapped[str] = mapped_column(String, nullable=False)
    # Canonical WUBRG-ordered string (e.g. "BG", "R", ""); CHECK in DB.
    color_identity: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    edition: Mapped[EditionModel] = relationship(
        "EditionModel",
        back_populates="cards",
        lazy="selectin",
    )
    card_types: Mapped[list["CardTypeModel"]] = relationship(
        "CardTypeModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    subtypes: Mapped[list["CardSubtypeModel"]] = relationship(
        "CardSubtypeModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    supertypes: Mapped[list["CardSupertypeModel"]] = relationship(
        "CardSupertypeModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    meta: Mapped["CardMetaModel | None"] = relationship(
        "CardMetaModel",
        back_populates="card",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    keywords: Mapped[list["CardKeywordModel"]] = relationship(
        "CardKeywordModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    card_tags: Mapped[list["CardTagModel"]] = relationship(
        "CardTagModel",
        primaryjoin="CardModel.oracle_id == foreign(CardTagModel.oracle_id)",
        viewonly=True,
        lazy="selectin",
    )
