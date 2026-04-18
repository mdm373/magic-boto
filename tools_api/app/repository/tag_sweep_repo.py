"""Repository for tag sweep run tables."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, exists, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    FAILED_BATCH_STATUSES,
    PROCESSABLE_BATCH_STATUSES,
    TERMINAL_BATCH_STATUSES,
    BatchModel,
    BatchStatus,
    CardModel,
    CardSupertypeModel,
    CardTypeModel,
    SweepRunStatus,
    TagModel,
    TagSweepBatchCardModel,
    TagSweepBatchModel,
    TagSweepModel,
)

from .batch_repo import BatchRepo


@dataclass(frozen=True, slots=True)
class SweepBatchRecord:
    """The oracle_id manifest for a submitted batch chunk — used to record cards in the DB."""

    custom_id: str
    oracle_ids: Sequence[str]


class TagSweepRepo:
    """Pure ORM access for sweep run, batch, and batch-card tables."""

    # ------------------------------------------------------------------
    # Sweep management
    # ------------------------------------------------------------------

    async def get_sweep(self, session: AsyncSession, sweep_id: uuid.UUID) -> TagSweepModel | None:
        """Return a sweep by ID, or None."""
        return await session.get(TagSweepModel, sweep_id)

    async def get_sweep_for_tag(
        self, session: AsyncSession, tag_id: uuid.UUID
    ) -> TagSweepModel | None:
        """Return the sweep row for this tag (at most one per tag), or None."""
        return cast(
            TagSweepModel | None,
            await session.scalar(select(TagSweepModel).where(TagSweepModel.tag_id == tag_id)),
        )

    async def get_open_sweep(
        self, session: AsyncSession, tag_id: uuid.UUID
    ) -> TagSweepModel | None:
        """Return the open sweep for this tag, or None."""
        return await session.scalar(  # type: ignore[no-any-return]
            select(TagSweepModel).where(
                TagSweepModel.tag_id == tag_id,
                TagSweepModel.status == SweepRunStatus.OPEN,
            )
        )

    async def create_sweep(self, session: AsyncSession, tag_id: uuid.UUID) -> TagSweepModel:
        """Open a sweep for this tag.

        Creates a new row on first use.  On subsequent calls (after a prior sweep
        completed) resets the existing row to OPEN and updates ``triggered_at``.
        ``completed_at`` is intentionally preserved — it acts as the epoch gate
        for card eligibility until the new sweep finishes and overwrites it.
        Caller must commit.
        """
        existing = await session.scalar(select(TagSweepModel).where(TagSweepModel.tag_id == tag_id))
        if existing is not None:
            existing.status = SweepRunStatus.OPEN
            existing.triggered_at = datetime.now(UTC)
            await session.flush()
            return existing
        sweep = TagSweepModel(tag_id=tag_id)
        session.add(sweep)
        await session.flush()
        return sweep

    async def complete_sweep(self, session: AsyncSession, sweep_id: uuid.UUID) -> None:
        """Mark the sweep complete and record the epoch timestamp. Caller must commit."""
        await session.execute(
            update(TagSweepModel)
            .where(TagSweepModel.id == sweep_id)
            .values(status=SweepRunStatus.COMPLETE, completed_at=datetime.now(UTC))
        )

    async def fail_sweep(self, session: AsyncSession, sweep_id: uuid.UUID) -> None:
        """Mark the sweep failed. Caller must commit."""
        await session.execute(
            update(TagSweepModel)
            .where(TagSweepModel.id == sweep_id)
            .values(status=SweepRunStatus.FAILED)
        )

    async def set_sweep_pipeline_process_options(
        self,
        session: AsyncSession,
        sweep_id: uuid.UUID,
        *,
        include_unsure: bool,
        include_excluded: bool,
        post_sweep_audit_id: uuid.UUID | None,
        requested_limit: int | None = None,
    ) -> None:
        """Persist pipeline options, optional kickoff limit, and optional audit row.

        Caller must commit.
        """
        sweep = await self.get_sweep(session, sweep_id)
        if sweep is None:
            raise ValueError(f"Sweep {sweep_id} not found.")
        sweep.pipeline_include_unsure = include_unsure
        sweep.pipeline_include_excluded = include_excluded
        sweep.post_sweep_audit_id = post_sweep_audit_id
        if requested_limit is not None:
            sweep.requested_limit = requested_limit
        await session.flush()

    async def delete_sweep_batch_history_for_tag(
        self, session: AsyncSession, tag_id: uuid.UUID
    ) -> int:
        """Delete all batch + batch-card records for a tag's sweeps.

        Deletes rows from ``batches`` whose IDs appear in ``tag_sweep_batches``
        for any sweep belonging to this tag.  The CASCADE on
        ``tag_sweep_batches.batch_id`` and ``tag_sweep_batch_cards.tag_sweep_batch_id``
        cleans up the child rows automatically.  The ``tag_sweep`` rows themselves
        are preserved so their ``completed_at`` epoch remains in place.

        Returns the number of batch rows deleted.
        """
        sweep_batch_ids = (
            select(TagSweepBatchModel.batch_id)
            .join(TagSweepModel, TagSweepBatchModel.tag_sweep_id == TagSweepModel.id)
            .where(TagSweepModel.tag_id == tag_id)
        )
        result = cast(
            CursorResult[tuple[()]],
            await session.execute(delete(BatchModel).where(BatchModel.id.in_(sweep_batch_ids))),
        )
        return result.rowcount or 0

    async def reset_epoch_for_tag(self, session: AsyncSession, tag_id: uuid.UUID) -> None:
        """Clear completed_at on the sweep row for this tag, resetting the epoch gate.

        After a full tag reset (all card_tags deleted), the epoch must be cleared so
        that cards which existed before the prior sweep's completed_at become eligible
        again on the next kickoff.  Caller must commit.
        """
        await session.execute(
            update(TagSweepModel).where(TagSweepModel.tag_id == tag_id).values(completed_at=None)
        )

    async def delete_open_sweep(self, session: AsyncSession, tag_id: uuid.UUID) -> uuid.UUID | None:
        """Delete the open sweep for a tag. Returns deleted sweep ID or None.

        Deletes linked ``batches`` rows first (same session) so outbox payloads are
        removed; FK CASCADE then drops ``tag_sweep_batches`` / ``tag_sweep_batch_cards``.
        """
        row = await session.scalar(
            select(TagSweepModel).where(
                TagSweepModel.tag_id == tag_id,
                TagSweepModel.status == SweepRunStatus.OPEN,
            )
        )
        if row is None:
            return None
        sweep_id = row.id
        sweep_batch_ids = select(TagSweepBatchModel.batch_id).where(
            TagSweepBatchModel.tag_sweep_id == sweep_id,
        )
        await session.execute(delete(BatchModel).where(BatchModel.id.in_(sweep_batch_ids)))
        await session.execute(delete(TagSweepModel).where(TagSweepModel.id == sweep_id))
        return sweep_id

    # ------------------------------------------------------------------
    # Batch management
    # ------------------------------------------------------------------

    async def record_pending_batch_with_cards(
        self,
        session: AsyncSession,
        sweep_id: uuid.UUID,
        chunks: Sequence[SweepBatchRecord],
    ) -> BatchModel:
        """Insert pending ``batches`` row, ``tag_sweep_batches``, and chunk card rows."""
        batch = await BatchRepo().create_pending_batch(session)

        total_cards = sum(len(chunk.oracle_ids) for chunk in chunks)
        sweep_batch = TagSweepBatchModel(
            tag_sweep_id=sweep_id,
            batch_id=batch.id,
            card_count=total_cards,
        )
        session.add(sweep_batch)
        await session.flush()

        for chunk in chunks:
            for position, oracle_id in enumerate(chunk.oracle_ids):
                session.add(
                    TagSweepBatchCardModel(
                        tag_sweep_batch_id=sweep_batch.id,
                        chunk_custom_id=chunk.custom_id,
                        oracle_id=oracle_id,
                        position=position,
                    )
                )
        await session.flush()
        return batch

    async def get_tag_sweep_batch_by_batch_id(
        self, session: AsyncSession, batch_id: uuid.UUID
    ) -> TagSweepBatchModel | None:
        """Return the ``tag_sweep_batches`` row for ``magic_boto.batches.id``, or None."""
        return cast(
            TagSweepBatchModel | None,
            await session.scalar(
                select(TagSweepBatchModel).where(TagSweepBatchModel.batch_id == batch_id).limit(1)
            ),
        )

    async def get_batches(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> Sequence[TagSweepBatchModel]:
        """Return all batches for a sweep, ordered by submission time, batch loaded."""
        result = await session.execute(
            select(TagSweepBatchModel)
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(TagSweepBatchModel.tag_sweep_id == sweep_id)
            .order_by(BatchModel.created_at)
            .options(selectinload(TagSweepBatchModel.batch))
        )
        return list(result.scalars().all())

    async def get_non_terminal_batches(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> Sequence[TagSweepBatchModel]:
        """Return sweep batches whose ``batches.status`` is not terminal."""
        result = await session.execute(
            select(TagSweepBatchModel)
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(
                TagSweepBatchModel.tag_sweep_id == sweep_id,
                BatchModel.status.not_in(TERMINAL_BATCH_STATUSES),
            )
            .order_by(BatchModel.created_at)
            .options(selectinload(TagSweepBatchModel.batch))
        )
        return list(result.scalars().all())

    async def get_processable_batches(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> Sequence[TagSweepBatchModel]:
        """Return batches for a sweep whose results can be downloaded and applied."""
        result = await session.execute(
            select(TagSweepBatchModel)
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(
                TagSweepBatchModel.tag_sweep_id == sweep_id,
                BatchModel.status.in_(PROCESSABLE_BATCH_STATUSES),
            )
            .order_by(BatchModel.created_at)
            .options(selectinload(TagSweepBatchModel.batch))
        )
        return list(result.scalars().all())

    async def get_batches_pending_submit(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> Sequence[TagSweepBatchModel]:
        """Return sweep batches still in outbox (not yet accepted by Anthropic Batch API)."""
        result = await session.execute(
            select(TagSweepBatchModel)
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(
                TagSweepBatchModel.tag_sweep_id == sweep_id,
                BatchModel.status == BatchStatus.PENDING_SUBMIT,
            )
            .order_by(BatchModel.created_at)
            .options(selectinload(TagSweepBatchModel.batch))
        )
        return list(result.scalars().all())

    async def are_all_batches_processed(self, session: AsyncSession, sweep_id: uuid.UUID) -> bool:
        """Return True if every batch for this sweep has status 'processed'."""
        batches = await self.get_batches(session, sweep_id)
        return bool(batches) and all(b.batch.status == BatchStatus.PROCESSED for b in batches)

    async def get_batch_cards(
        self,
        session: AsyncSession,
        tag_sweep_batch_id: uuid.UUID,
        chunk_custom_id: str,
    ) -> Sequence[TagSweepBatchCardModel]:
        """Return card rows for a chunk ordered by position."""
        result = await session.execute(
            select(TagSweepBatchCardModel)
            .where(
                TagSweepBatchCardModel.tag_sweep_batch_id == tag_sweep_batch_id,
                TagSweepBatchCardModel.chunk_custom_id == chunk_custom_id,
            )
            .order_by(TagSweepBatchCardModel.position)
        )
        return list(result.scalars().all())

    async def get_submitted_oracle_ids_for_sweep(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> frozenset[str]:
        """Return all oracle_ids submitted in any batch for this sweep."""
        result = await session.execute(
            select(TagSweepBatchCardModel.oracle_id)
            .join(
                TagSweepBatchModel,
                TagSweepBatchCardModel.tag_sweep_batch_id == TagSweepBatchModel.id,
            )
            .where(TagSweepBatchModel.tag_sweep_id == sweep_id)
            .distinct()
        )
        return frozenset(result.scalars().all())

    async def get_failed_oracle_ids_for_sweep(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> Sequence[str]:
        """Return oracle_ids that need re-enqueueing."""
        api_failed = await session.execute(
            select(TagSweepBatchCardModel.oracle_id)
            .join(
                TagSweepBatchModel,
                TagSweepBatchCardModel.tag_sweep_batch_id == TagSweepBatchModel.id,
            )
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(
                TagSweepBatchModel.tag_sweep_id == sweep_id,
                BatchModel.status.in_(FAILED_BATCH_STATUSES),
            )
        )

        parse_failed = await session.execute(
            select(TagSweepBatchCardModel.oracle_id)
            .join(
                TagSweepBatchModel,
                TagSweepBatchCardModel.tag_sweep_batch_id == TagSweepBatchModel.id,
            )
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(
                TagSweepBatchModel.tag_sweep_id == sweep_id,
                BatchModel.status == BatchStatus.PROCESSED,
                TagSweepBatchCardModel.failed.is_(True),
            )
        )

        seen: set[str] = set()
        results: list[str] = []
        for oracle_id in [*api_failed.scalars().all(), *parse_failed.scalars().all()]:
            if oracle_id not in seen:
                seen.add(oracle_id)
                results.append(oracle_id)
        return results

    async def mark_batch_cards_failed(
        self,
        session: AsyncSession,
        tag_sweep_batch_id: uuid.UUID,
        oracle_ids: Sequence[str],
    ) -> None:
        """Mark specific oracle_ids as failed within a batch. Caller must commit."""
        await session.execute(
            update(TagSweepBatchCardModel)
            .where(
                TagSweepBatchCardModel.tag_sweep_batch_id == tag_sweep_batch_id,
                TagSweepBatchCardModel.oracle_id.in_(oracle_ids),
            )
            .values(failed=True)
        )

    # ------------------------------------------------------------------
    # Card fetching / eligibility
    # ------------------------------------------------------------------

    async def fetch_eligible_oracle_ids(
        self,
        session: AsyncSession,
        tag: TagModel,
        sweep_id: uuid.UUID,
        limit: int = 0,
    ) -> Sequence[str]:
        """Return oracle_ids eligible for this sweep.

        Epoch gate: cards created at or before the sweep's ``completed_at`` are
        skipped — they were already evaluated.  Only cards ingested after that
        epoch (or all cards when no completed sweep exists yet) are considered.
        One sweep row per tag is assumed.
        """
        epoch_subq = (
            select(TagSweepModel.completed_at)
            .where(TagSweepModel.tag_id == tag.id)
            .scalar_subquery()
        )

        current_subq = (
            select(TagSweepBatchCardModel.oracle_id)
            .join(
                TagSweepBatchModel,
                TagSweepBatchCardModel.tag_sweep_batch_id == TagSweepBatchModel.id,
            )
            .where(TagSweepBatchModel.tag_sweep_id == sweep_id)
            .scalar_subquery()
        )

        stmt = (
            select(CardModel.oracle_id)
            .group_by(CardModel.oracle_id)
            .where(
                # Epoch gate: skip cards that existed when the last sweep completed.
                (epoch_subq.is_(None)) | (CardModel.created_at > epoch_subq),
                CardModel.oracle_id.not_in(current_subq),
            )
        )

        include_types = [r.card_type for r in tag.tag_types]
        if include_types:
            stmt = stmt.where(
                exists(
                    select(CardTypeModel.card_id).where(
                        CardTypeModel.card_id == CardModel.card_id,
                        CardTypeModel.card_type.in_(include_types),
                    )
                )
            )

        include_supertypes = [r.card_supertype for r in tag.supertypes]
        if include_supertypes:
            stmt = stmt.where(
                exists(
                    select(CardSupertypeModel.card_id).where(
                        CardSupertypeModel.card_id == CardModel.card_id,
                        CardSupertypeModel.card_supertype.in_(include_supertypes),
                    )
                )
            )

        stmt = stmt.order_by(CardModel.oracle_id)
        if limit > 0:
            stmt = stmt.limit(limit)

        return list((await session.execute(stmt)).scalars().all())

    async def is_sweep_complete(
        self,
        session: AsyncSession,
        sweep_id: uuid.UUID,
        tag: TagModel,
    ) -> bool:
        """Return True when all batches are processed and no eligible cards remain."""
        if not await self.are_all_batches_processed(session, sweep_id):
            return False
        remaining = await self.fetch_eligible_oracle_ids(session, tag, sweep_id)
        return len(remaining) == 0
