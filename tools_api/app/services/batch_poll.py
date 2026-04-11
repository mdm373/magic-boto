"""Shared batch-poll iteration for sweep and audit pipelines.

The poller returns remote status snapshots; :meth:`BatchRepo.apply_batch_poll_updates`
persists only changed rows. Caller (e.g. ``worker_session``) commits.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BatchStatus
from app.repository import BatchRepo, BatchStatusMeta

from .batch_client import BatchApiClient, create_batch_client


class BatchPollOutcome(enum.Enum):
    """Result of a single poll iteration — the only gate for 'ready to process'."""

    NO_BATCH_IDS = "no_batch_ids"
    ALL_TERMINAL = "all_terminal"
    IN_PROGRESS = "in_progress"


@dataclass(frozen=True, slots=True)
class BatchPollResult:
    """One poll step: gate outcome plus every non-terminal batch read from the API this round."""

    outcome: BatchPollOutcome
    batch_status_metas: Sequence[BatchStatusMeta]


class BatchPollProvider(Protocol):
    """Interface a pipeline implements to participate in the shared poll step."""

    async def fetch_batch_ids(self, session: AsyncSession) -> Sequence[uuid.UUID]:
        """Return all batch IDs for this pipeline run, regardless of status."""
        ...


class BatchPoller:
    """Runs a single Anthropic batch status sync for a pipeline (Celery reschedules until done)."""

    def __init__(
        self,
        provider: BatchPollProvider,
        batch_client: BatchApiClient,
        batch_repo: BatchRepo,
    ) -> None:
        self._provider = provider
        self._batch_client = batch_client
        self._batch_repo = batch_repo

    async def sync_with_anthropic(self, session: AsyncSession) -> BatchPollResult:
        """Fetch remote status for non-terminal batches, apply updates via repo, return outcome.

        Skips Anthropic entirely while any row is ``pending_submit`` (nothing to poll yet).
        """
        batch_ids = await self._provider.fetch_batch_ids(session)

        if not batch_ids:
            logger.info("No batches found for this run.")
            return BatchPollResult(BatchPollOutcome.NO_BATCH_IDS, ())

        rows = await self._batch_repo.get_batches_by_ids(session, batch_ids)
        found = {r.id for r in rows}
        missing = set(batch_ids) - found
        if missing:
            raise ValueError(f"Batch id(s) not found: {missing!r}")

        if any(r.status == BatchStatus.PENDING_SUBMIT for r in rows):
            logger.info("Batch(es) still pending_submit; defer poll.")
            return BatchPollResult(BatchPollOutcome.IN_PROGRESS, ())

        batches = await self._batch_repo.get_non_terminal_batches_by_ids(session, batch_ids)
        if not batches:
            logger.info("All batches are in a terminal state.")
            return BatchPollResult(BatchPollOutcome.ALL_TERMINAL, ())

        metas: list[BatchStatusMeta] = []
        for batch in batches:
            anthropic_id = batch.anthropic_batch_id
            assert anthropic_id is not None  # get_non_terminal_batches_by_ids filters nulls
            api = self._batch_client.get_batch_status(anthropic_id)
            metas.append(BatchStatusMeta(batch.id, api.processing_status, api.ended_at))
        await self._batch_repo.update_batch_status_meta(session, metas)
        still = await self._batch_repo.get_non_terminal_batches_by_ids(session, batch_ids)
        if not still:
            logger.info("All batches are in a terminal state.")
            return BatchPollResult(BatchPollOutcome.ALL_TERMINAL, metas)

        logger.info("{} batch(es) still in progress.", len(still))
        return BatchPollResult(BatchPollOutcome.IN_PROGRESS, metas)


def create_batch_poller(provider: BatchPollProvider) -> BatchPoller:
    return BatchPoller(
        provider=provider,
        batch_client=create_batch_client(),
        batch_repo=BatchRepo(),
    )
