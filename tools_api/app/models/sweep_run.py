"""ORM: ``magic_boto.tag_sweep`` (batch sweep run state per tag)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .sweep_status import SweepRunStatus


class TagSweepModel(Base):
    """One row per sweep epoch per tag.

    A run is 'open' while kickoff is submitting batches and process is applying tags.
    It becomes 'complete' once all batches are processed and no eligible cards remain.
    """

    __tablename__ = "tag_sweep"
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
