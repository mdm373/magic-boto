"""ORM: ``magic_boto.sweep_run_batch_cards`` (cards submitted per batch chunk)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SweepRunBatchCardModel(Base):
    """One row per oracle_id submitted within a chunk of a sweep_run_batch.

    position is the 0-based row index within the chunk — used to zip the
    Y/N/U response string back to oracle_ids at process time.
    """

    __tablename__ = "sweep_run_batch_cards"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sweep_run_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("magic_boto.sweep_run_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_custom_id: Mapped[str] = mapped_column(Text, nullable=False)
    oracle_id: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
