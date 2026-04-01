"""ORM: ``magic_boto.sweep_runs`` (batch sweep run state per tag)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .sweep_status import SweepRunStatus


class SweepRunModel(Base):
    """One row per sweep epoch per tag.

    A run is 'open' while kickoff is submitting batches and process is applying tags.
    It becomes 'complete' once process has applied all tags and all_cards_queued is True,
    at which point triggered_at becomes the epoch gate for the next sweep.
    """

    __tablename__ = "sweep_runs"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("magic_boto.tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default=SweepRunStatus.OPEN)
    last_submitted_oracle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    all_cards_queued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
