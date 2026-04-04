"""ORM: ``magic_boto.batches`` (Anthropic batch lifecycle, shared by sweep and audit)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .sweep_status import BatchStatus


class BatchModel(Base):
    """An Anthropic Messages Batch."""

    __tablename__ = "batches"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    anthropic_batch_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=BatchStatus.SUBMITTED)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
