"""Read-only sweep lookups (open run, linked batches)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SweepRunStatus, TagSweepModel
from app.repository import TagRepo, TagSweepRepo


class TagSweepService:
    """Tag sweep queries; no pipeline writes or batch creation."""

    def __init__(
        self,
        *,
        sweep_repo: TagSweepRepo,
        tag_repo: TagRepo,
    ) -> None:
        self._sweep_repo = sweep_repo
        self._tag_repo = tag_repo

    async def get_batch_ids_for_sweep(
        self, session: AsyncSession, sweep_id: uuid.UUID
    ) -> list[str]:
        """Return ``batches.id`` strings linked to the sweep (``TagSweepBatchModel`` rows)."""
        batches = await self._sweep_repo.get_batches(session, sweep_id)
        ids = [str(sb.batch_id) for sb in batches]
        if not ids:
            raise ValueError(f"No batches for sweep {sweep_id}.")
        return ids

    async def get_pending_batch_ids_for_sweep(
        self, session: AsyncSession, sweep: TagSweepModel
    ) -> list[str]:
        """Return batch id strings still ``pending_submit`` (outbox, not yet on Anthropic)."""
        batches = await self._sweep_repo.get_batches_pending_submit(session, sweep.id)
        ids = [str(sb.batch_id) for sb in batches]
        return ids

    async def get_open_sweep_batch_ids(self, session: AsyncSession, tag_name: str) -> list[str]:
        """Return ``batches.id`` strings for the tag's open sweep, or raise if missing/empty."""
        tag_m = await self._tag_repo.require_tag_model(session, tag_name)
        sweep = await self._sweep_repo.get_open_sweep(session, tag_m.id)
        if sweep is None:
            raise ValueError(f"No open sweep for tag {tag_name!r}.")
        return await self.get_batch_ids_for_sweep(session, sweep.id)

    async def require_open_sweep_for_batch_ids(
        self,
        session: AsyncSession,
        batch_ids: Sequence[uuid.UUID],
    ) -> TagSweepModel:
        """Return the open sweep that owns all given batch IDs (``tag_sweep_batches``)."""
        if not batch_ids:
            raise ValueError("batch_ids must be non-empty.")
        ids = frozenset(batch_ids)
        first_row = await self._sweep_repo.get_tag_sweep_batch_by_batch_id(session, next(iter(ids)))
        if first_row is None:
            raise ValueError("Batch id(s) are not linked to a tag sweep.")
        sweep_id = first_row.tag_sweep_id
        sweep = await self._sweep_repo.get_sweep(session, sweep_id)
        if sweep is None:
            raise ValueError(f"Sweep {sweep_id} not found.")
        if sweep.status != SweepRunStatus.OPEN:
            raise ValueError(f"Sweep {sweep_id} is not open (cannot process via pipeline).")
        linked = {sb.batch_id for sb in await self._sweep_repo.get_batches(session, sweep_id)}
        if not ids.issubset(linked):
            raise ValueError("One or more batch ids are not part of this sweep.")
        return sweep


def create_tag_sweep_service() -> TagSweepService:
    """Default wiring for CLIs and routes."""
    return TagSweepService(
        sweep_repo=TagSweepRepo(),
        tag_repo=TagRepo(),
    )


__all__ = ["TagSweepService", "create_tag_sweep_service"]
