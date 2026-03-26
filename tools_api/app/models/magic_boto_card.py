"""ORM: ``magic_boto.cards`` (one printing in the catalog)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .magic_boto_edition import MagicBotoEditionModel

if TYPE_CHECKING:
    from .magic_boto_card_keyword import MagicBotoCardKeywordModel
    from .magic_boto_card_meta import MagicBotoCardMetaModel
    from .magic_boto_card_subtype import MagicBotoCardSubtypeModel
    from .magic_boto_card_supertype import MagicBotoCardSupertypeModel
    from .magic_boto_card_type import MagicBotoCardTypeModel


class MagicBotoCardModel(Base):
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
    scryfall_id: Mapped[str | None] = mapped_column(String)
    # Canonical WUBRG-ordered string (e.g. "BG", "R", ""); CHECK in DB.
    color_identity: Mapped[str] = mapped_column(String, nullable=False, default="")

    edition: Mapped[MagicBotoEditionModel] = relationship(
        "MagicBotoEditionModel",
        back_populates="cards",
        lazy="selectin",
    )
    # Unquoted ``Mapped[list[...]]`` so SQLAlchemy sets ``uselist``.
    card_types: Mapped[list[MagicBotoCardTypeModel]] = relationship(
        "MagicBotoCardTypeModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    subtypes: Mapped[list[MagicBotoCardSubtypeModel]] = relationship(
        "MagicBotoCardSubtypeModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    supertypes: Mapped[list[MagicBotoCardSupertypeModel]] = relationship(
        "MagicBotoCardSupertypeModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    meta: Mapped[MagicBotoCardMetaModel | None] = relationship(
        "MagicBotoCardMetaModel",
        back_populates="card",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    keywords: Mapped[list[MagicBotoCardKeywordModel]] = relationship(
        "MagicBotoCardKeywordModel",
        back_populates="card",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
