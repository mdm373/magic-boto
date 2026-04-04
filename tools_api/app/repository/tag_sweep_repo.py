"""Repository for tag sweep run tables."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, exists, select, update
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


@dataclass(frozen=True, slots=True)
class BatchChunkRecord:
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

    async def get_open_sweep(
        self, session: AsyncSession, tag_id: uuid.UUID
    ) -> TagSweepModel | None:
        """Return the most recently created open sweep for this tag, or None."""
        result = await session.scalars(
            select(TagSweepModel)
            .where(TagSweepModel.tag_id == tag_id, TagSweepModel.status == SweepRunStatus.OPEN)
            .order_by(TagSweepModel.triggered_at.desc())
            .limit(1)
        )
        return result.first()

    async def create_sweep(self, session: AsyncSession, tag_id: uuid.UUID) -> TagSweepModel:
        """Create a new open sweep. Caller must commit."""
        sweep = TagSweepModel(tag_id=tag_id)
        session.add(sweep)
        await session.flush()
        return sweep

    async def complete_sweep(self, session: AsyncSession, sweep_id: uuid.UUID) -> None:
        """Mark the sweep complete. Caller must commit."""
        await session.execute(
            update(TagSweepModel)
            .where(TagSweepModel.id == sweep_id)
            .values(status=SweepRunStatus.COMPLETE)
        )

    async def fail_sweep(self, session: AsyncSession, sweep_id: uuid.UUID) -> None:
        """Mark the sweep failed. Caller must commit."""
        await session.execute(
            update(TagSweepModel)
            .where(TagSweepModel.id == sweep_id)
            .values(status=SweepRunStatus.FAILED)
        )

    async def delete_open_sweep(self, session: AsyncSession, tag_id: uuid.UUID) -> uuid.UUID | None:
        """Delete the open sweep for a tag. Returns deleted sweep ID or None."""
        row = await session.scalar(
            select(TagSweepModel)
            .where(TagSweepModel.tag_id == tag_id, TagSweepModel.status == SweepRunStatus.OPEN)
            .order_by(TagSweepModel.triggered_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        sweep_id = row.id
        await session.execute(delete(TagSweepModel).where(TagSweepModel.id == sweep_id))
        return sweep_id

    # ------------------------------------------------------------------
    # Batch management
    # ------------------------------------------------------------------

    async def record_batch_with_cards(
        self,
        session: AsyncSession,
        sweep_id: uuid.UUID,
        anthropic_batch_id: str,
        chunks: Sequence[BatchChunkRecord],
    ) -> BatchModel:
        """Insert a batches row, a tag_sweep_batches row, and all tag_sweep_batch_cards rows."""
        batch = BatchModel(anthropic_batch_id=anthropic_batch_id)
        session.add(batch)
        await session.flush()

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

    async def get_batches(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> Sequence[TagSweepBatchModel]:
        """Return all batches for a sweep, ordered by submission time, batch loaded."""
        result = await session.execute(
            select(TagSweepBatchModel)
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(TagSweepBatchModel.tag_sweep_id == sweep_id)
            .order_by(BatchModel.submitted_at)
            .options(selectinload(TagSweepBatchModel.batch))
        )
        return list(result.scalars().all())

    async def get_non_terminal_batches(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> Sequence[TagSweepBatchModel]:
        """Return batches for a sweep whose underlying batch is not yet in a terminal state."""
        result = await session.execute(
            select(TagSweepBatchModel)
            .join(BatchModel, TagSweepBatchModel.batch_id == BatchModel.id)
            .where(
                TagSweepBatchModel.tag_sweep_id == sweep_id,
                BatchModel.status.not_in(TERMINAL_BATCH_STATUSES),
            )
            .order_by(BatchModel.submitted_at)
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
            .order_by(BatchModel.submitted_at)
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
        """Return oracle_ids eligible for this sweep."""
        completed_subq = (
            select(TagSweepBatchCardModel.oracle_id)
            .join(
                TagSweepBatchModel,
                TagSweepBatchCardModel.tag_sweep_batch_id == TagSweepBatchModel.id,
            )
            .join(TagSweepModel, TagSweepBatchModel.tag_sweep_id == TagSweepModel.id)
            .where(
                TagSweepModel.tag_id == tag.id,
                TagSweepModel.status == SweepRunStatus.COMPLETE,
            )
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
                CardModel.oracle_id.not_in(completed_subq),
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
