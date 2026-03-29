"""ORM: ``magic_boto.card_tags`` junction (card ↔ tag)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MagicBotoCardTagModel(Base):
    """Junction table linking cards to user-defined tags."""

    __tablename__ = "card_tags"
    __table_args__ = {"schema": "magic_boto"}

    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("magic_boto.cards.card_id", ondelete="CASCADE"),
        primary_key=True,
    )
