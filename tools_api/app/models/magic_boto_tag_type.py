"""ORM: ``magic_boto.tag_types`` (card type include filter for a tag sweep)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .magic_boto_tag import MagicBotoTagModel


class MagicBotoTagTypeModel(Base):
    """Card type include filter for a tag sweep.

    When one or more rows exist for a tag, the sweep only processes oracle IDs
    whose cards have at least one matching card_type. No rows = no filter (all types).
    """

    __tablename__ = "tag_types"
    __table_args__ = {"schema": "magic_boto"}

    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_type: Mapped[str] = mapped_column(Text, primary_key=True)

    tag: Mapped[MagicBotoTagModel] = relationship(
        "MagicBotoTagModel",
        back_populates="tag_types",
    )
