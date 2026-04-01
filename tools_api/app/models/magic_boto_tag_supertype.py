"""ORM: ``magic_boto.tag_supertypes`` (supertype include filter for a tag sweep)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .magic_boto_tag import MagicBotoTagModel


class MagicBotoTagSupertypeModel(Base):
    """Card supertype include filter for a tag sweep.

    When one or more rows exist for a tag, the sweep only processes oracle IDs
    whose cards have at least one matching card_supertype. No rows = no filter (all supertypes).
    """

    __tablename__ = "tag_supertypes"
    __table_args__ = {"schema": "magic_boto"}

    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_supertype: Mapped[str] = mapped_column(Text, primary_key=True)

    tag: Mapped[MagicBotoTagModel] = relationship(
        "MagicBotoTagModel",
        back_populates="supertypes",
    )
