"""ORM: ``magic_boto.tag_audit`` (audit runs for tag quality review)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .batch_model import BatchModel


class TagAuditModel(Base):
    """One row per tag audit run.

    State is derived from the linked BatchModel and the report column:
    - batch_id is None → kickoff not yet run
    - batch_id set, report is None → batch pending or failed
    - report is not None → audit complete
    """

    __tablename__ = "tag_audit"
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
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_tagged_sample: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    audit_excluded_sample: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    audit_unsure_sample: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    batch: Mapped[BatchModel | None] = relationship("BatchModel", lazy="selectin")
