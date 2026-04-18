"""ORM: ``magic_boto.tag_sweep`` (batch sweep run state per tag)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .sweep_status import SweepRunStatus


class TagSweepModel(Base):
    """One row per sweep epoch per tag.

    A run is 'open' while kickoff is submitting batches and process is applying tags.
    It becomes 'complete' once all batches are processed and no eligible cards remain.
    ``completed_at`` is set when status transitions to COMPLETE and acts as the epoch
    gate: the next kickoff will only consider cards created after this timestamp.

    ``post_sweep_audit_id`` optionally references a pre-created ``tag_audit`` row (audit-after).
    After sweep processing, that audit is kicked off if the id is set.
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
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default=SweepRunStatus.OPEN)
    pipeline_include_unsure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pipeline_include_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    post_sweep_audit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.tag_audit.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Requested card limit for this sweep kickoff; 0 means 'all eligible'.",
    )
