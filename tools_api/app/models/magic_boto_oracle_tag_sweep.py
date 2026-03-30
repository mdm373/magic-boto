"""ORM: ``magic_boto.oracle_tag_sweeps`` (per-tag sweep progress state)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MagicBotoOracleTagSweepModel(Base):
    """Tracks sweep progress for a bot reviewing cards for a given tag.

    One row per tag. Deleting the parent tag cascades here automatically.
    Keyed by tag UUID so the tag can be renamed without affecting sweep state.
    """

    __tablename__ = "oracle_tag_sweeps"
    __table_args__ = {"schema": "magic_boto"}

    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("magic_boto.tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_swept_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor: Mapped[str | None] = mapped_column(nullable=True)
