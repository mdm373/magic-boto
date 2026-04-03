"""Sweep run service: manage sweep_runs / sweep_run_batches and fetch pending cards."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magic_boto_card import MagicBotoCardModel
from app.models.magic_boto_card_supertype import MagicBotoCardSupertypeModel
from app.models.magic_boto_card_type import MagicBotoCardTypeModel
from app.models.magic_boto_tag import MagicBotoTagModel
from app.models.sweep_run import SweepRunModel
from app.models.sweep_run_batch import SweepRunBatchModel
from app.models.sweep_run_batch_card import SweepRunBatchCardModel
from app.models.sweep_status import (
    PROCESSABLE_BATCH_STATUSES,
    TERMINAL_BATCH_STATUSES,
    BatchStatus,
    SweepRunStatus,
)
from app.tag.batch.client import BatchChunkRecord


class SweepRunService:
    """Manage sweep run lifecycle and card fetching for the batch sweep pipeline."""

    # ------------------------------------------------------------------
    # Run management
    # ------------------------------------------------------------------

    async def get_run(self, session: AsyncSession, run_id: uuid.UUID) -> SweepRunModel | None:
        """Return a sweep run by ID, or None."""
        return cast(
            SweepRunModel | None,
            await session.scalar(select(SweepRunModel).where(SweepRunModel.id == run_id)),
        )

    async def get_open_run(self, session: AsyncSession, tag_id: uuid.UUID) -> SweepRunModel | None:
        """Return the most recently created open run for this tag, or None."""
        return cast(
            SweepRunModel | None,
            await session.scalar(
                select(SweepRunModel)
                .where(SweepRunModel.tag_id == tag_id, SweepRunModel.status == SweepRunStatus.OPEN)
                .order_by(SweepRunModel.triggered_at.desc())
                .limit(1)
            ),
        )

    async def create_run(self, session: AsyncSession, tag_id: uuid.UUID) -> SweepRunModel:
        """Create a new open run. Caller must commit."""
        run = SweepRunModel(tag_id=tag_id)
        session.add(run)
        await session.flush()
        return run

    async def complete_run(self, session: AsyncSession, run_id: uuid.UUID) -> None:
        """Mark the run complete. Caller must commit."""
        await session.execute(
            update(SweepRunModel)
            .where(SweepRunModel.id == run_id)
            .values(status=SweepRunStatus.COMPLETE)
        )

    async def fail_run(self, session: AsyncSession, run_id: uuid.UUID) -> None:
        """Mark the run failed. Caller must commit."""
        await session.execute(
            update(SweepRunModel)
            .where(SweepRunModel.id == run_id)
            .values(status=SweepRunStatus.FAILED)
        )

    async def delete_open_run(self, session: AsyncSession, tag_id: uuid.UUID) -> uuid.UUID | None:
        """Delete the open run for a tag (cascades to batches). Returns deleted run ID or None."""
        row = await session.scalar(
            select(SweepRunModel)
            .where(SweepRunModel.tag_id == tag_id, SweepRunModel.status == SweepRunStatus.OPEN)
            .order_by(SweepRunModel.triggered_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        run_id = row.id
        await session.execute(delete(SweepRunModel).where(SweepRunModel.id == run_id))
        return run_id

    # ------------------------------------------------------------------
    # Batch management
    # ------------------------------------------------------------------

    async def record_batch_with_cards(
        self,
        session: AsyncSession,
        run_id: uuid.UUID,
        batch_id: str,
        chunks: Sequence[BatchChunkRecord],
    ) -> None:
        """Insert a sweep_run_batches row and all sweep_run_batch_cards rows.

        Flushes but does not commit — caller commits.
        """
        total_cards = sum(len(chunk.oracle_ids) for chunk in chunks)
        batch_row = SweepRunBatchModel(
            run_id=run_id,
            batch_id=batch_id,
            card_count=total_cards,
        )
        session.add(batch_row)
        await session.flush()

        for chunk in chunks:
            for position, oracle_id in enumerate(chunk.oracle_ids):
                session.add(
                    SweepRunBatchCardModel(
                        sweep_run_batch_id=batch_row.id,
                        chunk_custom_id=chunk.custom_id,
                        oracle_id=oracle_id,
                        position=position,
                    )
                )
        await session.flush()

    async def get_batches(
        self, session: AsyncSession, run_id: uuid.UUID
    ) -> Sequence[SweepRunBatchModel]:
        """Return all batches for a run ordered by submission time."""
        result = await session.execute(
            select(SweepRunBatchModel)
            .where(SweepRunBatchModel.run_id == run_id)
            .order_by(SweepRunBatchModel.submitted_at)
        )
        return list(result.scalars().all())

    async def get_non_terminal_batches(
        self, session: AsyncSession, run_id: uuid.UUID
    ) -> Sequence[SweepRunBatchModel]:
        """Return batches that have not yet reached a terminal state."""
        result = await session.execute(
            select(SweepRunBatchModel)
            .where(
                SweepRunBatchModel.run_id == run_id,
                SweepRunBatchModel.status.not_in(TERMINAL_BATCH_STATUSES),
            )
            .order_by(SweepRunBatchModel.submitted_at)
        )
        return list(result.scalars().all())

    async def get_processable_batches(
        self, session: AsyncSession, run_id: uuid.UUID
    ) -> Sequence[SweepRunBatchModel]:
        """Return batches whose results can be downloaded and applied."""
        result = await session.execute(
            select(SweepRunBatchModel)
            .where(
                SweepRunBatchModel.run_id == run_id,
                SweepRunBatchModel.status.in_(PROCESSABLE_BATCH_STATUSES),
            )
            .order_by(SweepRunBatchModel.submitted_at)
        )
        return list(result.scalars().all())

    async def are_all_batches_processed(self, session: AsyncSession, run_id: uuid.UUID) -> bool:
        """Return True if every batch for this run has status 'processed'."""
        batches = await self.get_batches(session, run_id)
        return bool(batches) and all(b.status == BatchStatus.PROCESSED for b in batches)

    async def update_batch_status(
        self,
        session: AsyncSession,
        batch_id: str,
        status: str,
        completed_at: datetime | None = None,
    ) -> None:
        """Update batch status (and optionally completed_at). Caller must commit."""
        values: dict[str, object] = {"status": status}
        if completed_at is not None:
            values["completed_at"] = completed_at
        await session.execute(
            update(SweepRunBatchModel)
            .where(SweepRunBatchModel.batch_id == batch_id)
            .values(**values)
        )

    async def mark_batch_processed(self, session: AsyncSession, batch_id: str) -> None:
        """Transition batch status to 'processed'. Caller must commit."""
        await self.update_batch_status(
            session, batch_id, BatchStatus.PROCESSED, completed_at=datetime.now(UTC)
        )

    async def get_batch_cards(
        self,
        session: AsyncSession,
        sweep_run_batch_id: uuid.UUID,
        chunk_custom_id: str,
    ) -> Sequence[SweepRunBatchCardModel]:
        """Return card rows for a chunk ordered by position."""
        result = await session.execute(
            select(SweepRunBatchCardModel)
            .where(
                SweepRunBatchCardModel.sweep_run_batch_id == sweep_run_batch_id,
                SweepRunBatchCardModel.chunk_custom_id == chunk_custom_id,
            )
            .order_by(SweepRunBatchCardModel.position)
        )
        return list(result.scalars().all())

    async def get_submitted_oracle_ids_for_run(
        self, session: AsyncSession, run_id: uuid.UUID
    ) -> frozenset[str]:
        """Return all oracle_ids submitted in any batch for this run."""
        card_batch_join = SweepRunBatchCardModel.sweep_run_batch_id == SweepRunBatchModel.id
        result = await session.execute(
            select(SweepRunBatchCardModel.oracle_id)
            .join(SweepRunBatchModel, card_batch_join)
            .where(SweepRunBatchModel.run_id == run_id)
            .distinct()
        )
        return frozenset(result.scalars().all())

    async def get_failed_oracle_ids_for_run(
        self, session: AsyncSession, run_id: uuid.UUID
    ) -> Sequence[str]:
        """Return oracle_ids that need re-enqueueing.

        Covers two failure modes:
        - Batches that reached a non-processed terminal state (errored/expired/canceled).
        - Individual cards marked failed within an otherwise-processed batch
          (e.g. unparseable model response for their chunk).
        """
        card_batch_join = SweepRunBatchCardModel.sweep_run_batch_id == SweepRunBatchModel.id

        # Anthropic-level batch failures.
        api_failed_statuses = {"errored", "expired", "canceled"}
        api_failed = await session.execute(
            select(SweepRunBatchCardModel.oracle_id)
            .join(SweepRunBatchModel, card_batch_join)
            .where(
                SweepRunBatchModel.run_id == run_id,
                SweepRunBatchModel.status.in_(api_failed_statuses),
            )
        )

        # Parse-level failures: cards flagged failed within a processed batch.
        parse_failed = await session.execute(
            select(SweepRunBatchCardModel.oracle_id)
            .join(SweepRunBatchModel, card_batch_join)
            .where(
                SweepRunBatchModel.run_id == run_id,
                SweepRunBatchModel.status == BatchStatus.PROCESSED,
                SweepRunBatchCardModel.failed.is_(True),
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
        sweep_run_batch_id: uuid.UUID,
        oracle_ids: Sequence[str],
    ) -> None:
        """Mark specific oracle_ids as failed within a batch. Caller must commit."""
        await session.execute(
            update(SweepRunBatchCardModel)
            .where(
                SweepRunBatchCardModel.sweep_run_batch_id == sweep_run_batch_id,
                SweepRunBatchCardModel.oracle_id.in_(oracle_ids),
            )
            .values(failed=True)
        )

    # ------------------------------------------------------------------
    # Card fetching / eligibility
    # ------------------------------------------------------------------

    async def fetch_eligible_oracle_ids(
        self,
        session: AsyncSession,
        tag: MagicBotoTagModel,
        run_id: uuid.UUID,
        limit: int = 0,
    ) -> Sequence[str]:
        """Return oracle_ids eligible for this sweep run.

        Excludes:
        - oracle_ids already swept in any completed run for this tag
        - oracle_ids already submitted in the current open run (resumption)

        Applies tag type/supertype filters. Returns oracle_ids only — caller
        fetches card details via fetch_cards_by_oracle_ids.
        """
        card_batch_join = SweepRunBatchCardModel.sweep_run_batch_id == SweepRunBatchModel.id

        # Subquery: oracle_ids covered by a completed run for this tag.
        completed_subq = (
            select(SweepRunBatchCardModel.oracle_id)
            .join(SweepRunBatchModel, card_batch_join)
            .join(SweepRunModel, SweepRunBatchModel.run_id == SweepRunModel.id)
            .where(
                SweepRunModel.tag_id == tag.id,
                SweepRunModel.status == SweepRunStatus.COMPLETE,
            )
            .scalar_subquery()
        )

        # Subquery: oracle_ids already submitted in the current run.
        current_subq = (
            select(SweepRunBatchCardModel.oracle_id)
            .join(SweepRunBatchModel, card_batch_join)
            .where(SweepRunBatchModel.run_id == run_id)
            .scalar_subquery()
        )

        stmt = (
            select(MagicBotoCardModel.oracle_id)
            .group_by(MagicBotoCardModel.oracle_id)
            .where(
                MagicBotoCardModel.oracle_id.not_in(completed_subq),
                MagicBotoCardModel.oracle_id.not_in(current_subq),
            )
        )

        include_types = [r.card_type for r in tag.tag_types]
        if include_types:
            stmt = stmt.where(
                exists(
                    select(MagicBotoCardTypeModel.card_id).where(
                        MagicBotoCardTypeModel.card_id == MagicBotoCardModel.card_id,
                        MagicBotoCardTypeModel.card_type.in_(include_types),
                    )
                )
            )

        include_supertypes = [r.card_supertype for r in tag.supertypes]
        if include_supertypes:
            stmt = stmt.where(
                exists(
                    select(MagicBotoCardSupertypeModel.card_id).where(
                        MagicBotoCardSupertypeModel.card_id == MagicBotoCardModel.card_id,
                        MagicBotoCardSupertypeModel.card_supertype.in_(include_supertypes),
                    )
                )
            )

        stmt = stmt.order_by(MagicBotoCardModel.oracle_id)
        if limit > 0:
            stmt = stmt.limit(limit)

        return list((await session.execute(stmt)).scalars().all())

    async def fetch_cards_by_oracle_ids(
        self, session: AsyncSession, oracle_ids: Sequence[str]
    ) -> Sequence[MagicBotoCardModel]:
        """Return one representative card per oracle_id for the given IDs."""
        if not oracle_ids:
            return []
        all_cards = list(
            (
                await session.execute(
                    select(MagicBotoCardModel)
                    .where(MagicBotoCardModel.oracle_id.in_(oracle_ids))
                    .order_by(MagicBotoCardModel.oracle_id, MagicBotoCardModel.card_id)
                )
            )
            .scalars()
            .all()
        )
        seen: dict[str, MagicBotoCardModel] = {}
        for card in all_cards:
            if card.oracle_id not in seen:
                seen[card.oracle_id] = card
        return [seen[oid] for oid in oracle_ids if oid in seen]

    async def is_run_complete(
        self,
        session: AsyncSession,
        run_id: uuid.UUID,
        tag: MagicBotoTagModel,
    ) -> bool:
        """Return True when all batches are processed and no eligible cards remain."""
        if not await self.are_all_batches_processed(session, run_id):
            return False
        remaining = await self.fetch_eligible_oracle_ids(session, tag, run_id)
        return len(remaining) == 0


def create_sweep_run_service() -> SweepRunService:
    """Create a SweepRunService instance."""
    return SweepRunService()
