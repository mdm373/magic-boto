"""ORM: ``magic_boto`` tags table."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .tag_supertype_model import TagSupertypeModel
    from .tag_type_model import TagTypeModel


class TagModel(Base):
    """User-defined tag; ``name`` is stored trimmed and lowercased."""

    __tablename__ = "tags"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    tag_types: Mapped[list["TagTypeModel"]] = relationship(
        "TagTypeModel",
        back_populates="tag",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    supertypes: Mapped[list["TagSupertypeModel"]] = relationship(
        "TagSupertypeModel",
        back_populates="tag",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
