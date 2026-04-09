"""Repository for the shared ``batches`` table."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TERMINAL_BATCH_STATUSES, BatchModel, BatchStatus


@dataclass(frozen=True, slots=True)
class BatchStatusMeta:
    """Desired row state from an Anthropic batch poll (maps ``ended_at`` → ``completed_at``)."""

    batch_id: uuid.UUID
    status: str
    ended_at: datetime | None


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

    async def update_batch_status_meta(
        self,
        session: AsyncSession,
        updates: Sequence[BatchStatusMeta],
    ) -> None:
        """Set ``status`` / ``completed_at`` only when they differ from the row. Caller commits."""
        if not updates:
            return
        ids = [u.batch_id for u in updates]
        result = await session.execute(select(BatchModel).where(BatchModel.id.in_(ids)))
        by_id: dict[uuid.UUID, BatchModel] = {row.id: row for row in result.scalars().all()}
        for u in updates:
            row = by_id.get(u.batch_id)
            if row is None:
                continue
            if row.status == u.status and row.completed_at == u.ended_at:
                continue
            row.status = u.status
            row.completed_at = u.ended_at

    def mark_batch_processed(self, batch: BatchModel) -> None:
        """Set status to PROCESSED and stamp completed_at. Caller must commit."""
        batch.status = BatchStatus.PROCESSED
        batch.completed_at = datetime.now(UTC)
