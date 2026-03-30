"""ORM: ``magic_boto.oracle_tag_sweeps`` (per-tag sweep progress state)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MagicBotoOracleTagSweepModel(Base):
    """Tracks sweep progress for a bot reviewing cards for a given tag.

    One row per tag. Deleting the parent tag cascades here automatically.
    """

    __tablename__ = "oracle_tag_sweeps"
    __table_args__ = {"schema": "magic_boto"}

    tag_name: Mapped[str] = mapped_column(
        String,
        ForeignKey("magic_boto.tags.name", ondelete="CASCADE"),
        primary_key=True,
    )
    last_swept_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # NULL = no completed sweep yet
    cursor: Mapped[str | None] = mapped_column(String, nullable=True)
    # Last oracle_id processed in the current sweep; NULL = start of sweep
