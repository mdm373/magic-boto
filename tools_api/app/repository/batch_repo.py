"""Repository for the shared ``batches`` table."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
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

    async def create_pending_batch(self, session: AsyncSession) -> BatchModel:
        """Insert an outbox batch row (:attr:`~app.models.BatchStatus.PENDING_SUBMIT`)."""
        batch = BatchModel(anthropic_batch_id=None)
        session.add(batch)
        await session.flush()
        return batch

    async def get_batch(self, session: AsyncSession, batch_id: uuid.UUID) -> BatchModel | None:
        """Return a batch by id, or None."""
        return await session.get(BatchModel, batch_id)

    async def get_batches_by_ids(
        self, session: AsyncSession, batch_ids: Sequence[uuid.UUID]
    ) -> Sequence[BatchModel]:
        """Return all batches matching ids (order not preserved)."""
        if not batch_ids:
            return ()
        result = await session.execute(select(BatchModel).where(BatchModel.id.in_(batch_ids)))
        return list(result.scalars().all())

    async def get_non_terminal_batches_by_ids(
        self, session: AsyncSession, batch_ids: Sequence[uuid.UUID]
    ) -> Sequence[BatchModel]:
        """Return non-terminal batches that already have an Anthropic batch id (pollable)."""
        result = await session.execute(
            select(BatchModel).where(
                BatchModel.id.in_(batch_ids),
                BatchModel.anthropic_batch_id.is_not(None),
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
        await session.flush()

    async def mark_batch_processed(self, session: AsyncSession, batch: BatchModel) -> None:
        """Set status to PROCESSED and stamp completed_at. Caller commits."""
        batch.status = BatchStatus.PROCESSED
        batch.completed_at = datetime.now(UTC)
        await session.flush()

    async def set_batch_payload(
        self,
        session: AsyncSession,
        batch: BatchModel,
        payload: str,
    ) -> None:
        """Set outbox ``payload``. Caller commits."""
        batch.payload = payload
        await session.flush()

    async def apply_outbox_anthropic_batch_id(
        self, session: AsyncSession, batch_id: uuid.UUID, anthropic_batch_id: str
    ) -> None:
        """Store Anthropic batch id, clear ``payload``, move to ``submitted``. Caller commits."""
        batch = await self.get_batch(session, batch_id)
        if batch is None:
            raise ValueError(f"Batch {batch_id} not found.")
        batch.anthropic_batch_id = anthropic_batch_id
        batch.payload = None
        batch.status = BatchStatus.SUBMITTED
        batch.submitted_at = datetime.now(UTC)
        await session.flush()

    async def delete_batches_with_status_in(
        self, session: AsyncSession, statuses: Sequence[BatchStatus]
    ) -> int:
        """Delete rows whose ``status`` is in ``statuses``.

        Returns deleted row count. Caller commits. ``tag_sweep_batches`` rows cascade;
        ``tag_audit.batch_id`` is set null.
        """
        if not statuses:
            return 0
        values = tuple(s.value for s in statuses)
        result = await session.execute(delete(BatchModel).where(BatchModel.status.in_(values)))
        return int(cast(CursorResult[object], result).rowcount or 0)
