"""Sweep run service: manage sweep_runs / sweep_run_batches and fetch pending cards."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magic_boto_card import MagicBotoCardModel
from app.models.magic_boto_card_supertype import MagicBotoCardSupertypeModel
from app.models.magic_boto_card_type import MagicBotoCardTypeModel
from app.models.magic_boto_tag import MagicBotoTagModel
from app.models.sweep_run import SweepRunModel
from app.models.sweep_run_batch import SweepRunBatchModel
from app.models.sweep_status import (
    PROCESSABLE_BATCH_STATUSES,
    TERMINAL_BATCH_STATUSES,
    BatchStatus,
    SweepRunStatus,
)


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

    async def mark_all_cards_queued(self, session: AsyncSession, run_id: uuid.UUID) -> None:
        """Signal that kickoff has submitted every eligible card for this epoch."""
        await session.execute(
            update(SweepRunModel).where(SweepRunModel.id == run_id).values(all_cards_queued=True)
        )

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

    async def get_epoch_gate(self, session: AsyncSession, tag_id: uuid.UUID) -> datetime | None:
        """Return triggered_at of the last complete run, or None (first-ever sweep)."""
        return cast(
            datetime | None,
            await session.scalar(
                select(func.max(SweepRunModel.triggered_at)).where(
                    SweepRunModel.tag_id == tag_id,
                    SweepRunModel.status == SweepRunStatus.COMPLETE,
                )
            ),
        )

    # ------------------------------------------------------------------
    # Batch management
    # ------------------------------------------------------------------

    async def record_batch(
        self,
        session: AsyncSession,
        run_id: uuid.UUID,
        batch_id: str,
        card_count: int,
        last_oracle_id: str,
    ) -> None:
        """Insert a sweep_run_batches row and advance the run cursor. Caller must commit."""
        session.add(
            SweepRunBatchModel(
                run_id=run_id,
                batch_id=batch_id,
                card_count=card_count,
            )
        )
        await session.flush()
        await session.execute(
            update(SweepRunModel)
            .where(SweepRunModel.id == run_id)
            .values(last_submitted_oracle_id=last_oracle_id)
        )

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

    # ------------------------------------------------------------------
    # Card fetching
    # ------------------------------------------------------------------

    async def fetch_all_pending(
        self,
        session: AsyncSession,
        tag: MagicBotoTagModel,
        last_swept_at: datetime | None,
        after_oracle_id: str | None,
        limit: int,
    ) -> Sequence[MagicBotoCardModel]:
        """Return up to ``limit`` cards eligible for this sweep epoch.

        Applies the same eligibility logic as the old OracleTagSweepService:
        - Only oracle_ids whose MIN(created_at) > last_swept_at (skips prior epochs).
        - Respects the tag's sweep_include_types and sweep_include_supertypes filters.
        - Ordered by oracle_id; starts strictly after after_oracle_id (cursor).
        - last_swept_at=None → all cards eligible (first-ever sweep).
        """
        base = select(MagicBotoCardModel.oracle_id).group_by(MagicBotoCardModel.oracle_id)

        if last_swept_at is not None:
            base = base.having(func.min(MagicBotoCardModel.created_at) > last_swept_at)

        include_types = [r.card_type for r in tag.tag_types]
        if include_types:
            base = base.where(
                exists(
                    select(MagicBotoCardTypeModel.card_id).where(
                        MagicBotoCardTypeModel.card_id == MagicBotoCardModel.card_id,
                        MagicBotoCardTypeModel.card_type.in_(include_types),
                    )
                )
            )

        include_supertypes = [r.card_supertype for r in tag.supertypes]
        if include_supertypes:
            base = base.where(
                exists(
                    select(MagicBotoCardSupertypeModel.card_id).where(
                        MagicBotoCardSupertypeModel.card_id == MagicBotoCardModel.card_id,
                        MagicBotoCardSupertypeModel.card_supertype.in_(include_supertypes),
                    )
                )
            )

        if after_oracle_id is not None:
            base = base.where(MagicBotoCardModel.oracle_id > after_oracle_id)

        base = base.order_by(MagicBotoCardModel.oracle_id).limit(limit)

        oracle_ids: list[str] = list((await session.execute(base)).scalars().all())
        if not oracle_ids:
            return []

        cards_stmt = (
            select(MagicBotoCardModel)
            .where(MagicBotoCardModel.oracle_id.in_(oracle_ids))
            .order_by(MagicBotoCardModel.oracle_id, MagicBotoCardModel.card_id)
        )
        all_cards = list((await session.execute(cards_stmt)).scalars().all())

        seen: dict[str, MagicBotoCardModel] = {}
        for card in all_cards:
            if card.oracle_id not in seen:
                seen[card.oracle_id] = card

        return [seen[oid] for oid in oracle_ids if oid in seen]

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


def create_sweep_run_service() -> SweepRunService:
    """Create a SweepRunService instance."""
    return SweepRunService()
