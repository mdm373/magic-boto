"""ORM: ``magic_boto.tag_sweep_batches`` (Anthropic batches submitted for a tag sweep)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .batch_model import BatchModel


class TagSweepBatchModel(Base):
    """One row per Anthropic Messages Batch submitted for a tag sweep run."""

    __tablename__ = "tag_sweep_batches"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tag_sweep_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("magic_boto.tag_sweep.id", ondelete="CASCADE"),
        nullable=False,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    card_count: Mapped[int] = mapped_column(Integer, nullable=False)

    batch: Mapped[BatchModel] = relationship("BatchModel", lazy="selectin")
