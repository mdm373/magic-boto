"""Repository for the shared ``batches`` table."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TERMINAL_BATCH_STATUSES, BatchModel, BatchStatus


class BatchRepo:
    """Pure ORM access for the shared ``batches`` table."""

    async def create_batch(self, session: AsyncSession, anthropic_batch_id: str) -> BatchModel:
        """Insert a new batch row and flush. Caller must commit."""
        batch = BatchModel(anthropic_batch_id=anthropic_batch_id)
        session.add(batch)
        await session.flush()
        return batch

    async def get_non_terminal_batches_by_ids(
        self, session: AsyncSession, batch_ids: Sequence[uuid.UUID]
    ) -> Sequence[BatchModel]:
        """Return BatchModel rows for *batch_ids* that are not yet in a terminal state."""
        result = await session.execute(
            select(BatchModel).where(
                BatchModel.id.in_(batch_ids),
                BatchModel.status.not_in(TERMINAL_BATCH_STATUSES),
            )
        )
        return list(result.scalars().all())

    def mark_batch_processed(self, batch: BatchModel) -> None:
        """Set status to PROCESSED and stamp completed_at. Caller must commit."""
        batch.status = BatchStatus.PROCESSED
        batch.completed_at = datetime.now(UTC)
