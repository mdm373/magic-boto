"""Queue tag sweep batch work and configure the poll/process pipeline before Celery enqueue.

Celery ``submit_batch`` sends chunks to Anthropic; ``process_sweep_run`` polls and applies.
Pass one :class:`~sqlalchemy.ext.asyncio.AsyncSession` into :meth:`TagSweepInitializer.kickoff`
with a :class:`SweepKickoffRequest` (same scope as commit).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.message_schema import SWEEP_VERDICT_SCHEMA_PATH
from app.models import CardModel, TagModel, TagSweepModel
from app.repository import (
    BatchRepo,
    CardRepo,
    SweepBatchRecord,
    TagAuditRepo,
    TagRepo,
    TagSweepRepo,
)
from settings import get_settings

from .batch_client import Request
from .batch_serialization_service import (
    BatchSerializationService,
    create_batch_serialization_service,
)
from .card_payload import cards_to_csv
from .sweep_prompt_format import format_sweep_system_prompt

__all__ = [
    "SweepKickoffRequest",
    "TagSweepInitializer",
    "create_tag_sweep_initializer",
    "format_sweep_system_prompt",
]


@dataclass(frozen=True, slots=True)
class SweepKickoffRequest:
    """Parameters for :meth:`TagSweepInitializer.kickoff` (pending batch + pipeline options)."""

    tag_name: str
    limit: int
    reenqueue_failed: bool
    include_unsure: bool = True
    include_excluded: bool = True
    audit_after: bool = False
    audit_tagged_sample: int = 20
    audit_excluded_sample: int = 40
    audit_unsure_sample: int = 10


class TagSweepInitializer:
    """Create or resume a sweep run, persist pending batches, and set pipeline process options."""

    def __init__(
        self,
        *,
        sweep_repo: TagSweepRepo,
        tag_repo: TagRepo,
        audit_repo: TagAuditRepo,
        batch_serialization: BatchSerializationService,
    ) -> None:
        self._sweep_repo = sweep_repo
        self._tag_repo = tag_repo
        self._audit_repo = audit_repo
        self._batch_serialization = batch_serialization

    async def init_sweep(
        self, session: AsyncSession, request: SweepKickoffRequest
    ) -> TagSweepModel:
        """Open or resume a run, create pending batch(es), set pipeline options."""
        settings = get_settings()
        tag = await self._tag_repo.require_tag_model(session, request.tag_name)
        sweep = await self._ensure_sweep_run(session, tag)
        sweep_id = sweep.id
        reenqueue_failed = request.reenqueue_failed
        limit = request.limit
        logger.info("Sweep ID: {}", sweep.id)
        logger.info("Using model: {}", settings.tag_sweep_model)
        await self._create_new_batches(session, sweep_id, tag, reenqueue_failed, limit)
        await self._configure_pipeline(session, tag, sweep_id, request)
        return sweep

    async def _ensure_sweep_run(self, session: AsyncSession, tag: TagModel) -> TagSweepModel:
        run = await self._sweep_repo.get_open_sweep(session, tag.id)
        if run is not None:
            logger.info("Resuming existing run {}.", run.id)
            return run

        run = await self._sweep_repo.create_sweep(session, tag.id)
        logger.info("Created new sweep run.")
        return run

    async def _configure_pipeline(
        self,
        session: AsyncSession,
        tag_m: TagModel,
        sweep_id: uuid.UUID,
        request: SweepKickoffRequest,
    ) -> None:
        post_audit_id: uuid.UUID | None = None
        if request.audit_after:
            audit = await self._audit_repo.create_audit(
                session,
                tag_m.id,
                audit_tagged_sample=request.audit_tagged_sample,
                audit_excluded_sample=request.audit_excluded_sample,
                audit_unsure_sample=request.audit_unsure_sample,
            )
            post_audit_id = audit.id
        await self._sweep_repo.set_sweep_pipeline_process_options(
            session,
            sweep_id,
            include_unsure=request.include_unsure,
            include_excluded=request.include_excluded,
            post_sweep_audit_id=post_audit_id,
        )

    async def _create_new_batches(
        self,
        session: AsyncSession,
        sweep_id: uuid.UUID,
        tag: TagModel,
        reenqueue_failed: bool,
        limit: int,
    ) -> None:
        if reenqueue_failed:
            failed_ids = await self._sweep_repo.get_failed_oracle_ids_for_sweep(session, sweep_id)
            if not failed_ids:
                raise RuntimeError("Re-enqueue flagged for run with no failed ids")

            logger.info("Re-enqueueing {} failed oracle ID(s).", len(failed_ids))
            await self._create_pending_batch(session, sweep_id, tag, failed_ids)
            return

        eligible = await self._sweep_repo.fetch_eligible_oracle_ids(session, tag, sweep_id, limit)
        if not eligible:
            raise RuntimeError("No eligible cards to sweep")

        logger.info("{} eligible card(s) to submit.", len(eligible))
        await self._create_pending_batch(session, sweep_id, tag, eligible)

    async def _create_pending_batch(
        self,
        session: AsyncSession,
        run_id: uuid.UUID,
        tag: TagModel,
        oracle_ids: Sequence[str],
    ) -> None:
        """Persist chunk rows, outbox ``payload``, and a pending ``batches`` row."""
        settings = get_settings()
        chunk_size = settings.tag_sweep_batch_size
        records = [
            SweepBatchRecord(
                custom_id=f"chunk_{i // chunk_size}",
                oracle_ids=oracle_ids[i : i + chunk_size],
            )
            for i in range(0, len(oracle_ids), chunk_size)
        ]
        if len(records) > settings.batch_api_max_requests:
            raise RuntimeError(
                f"Chunk count {len(records)} exceeds batch_api_max_requests "
                f"({settings.batch_api_max_requests}). Reduce --limit or increase chunk size."
            )

        batch = await self._sweep_repo.record_pending_batch_with_cards(session, run_id, records)
        requests = await _build_sweep_batch_requests(session, tag.description, records)
        await BatchRepo().set_batch_payload(
            session,
            batch,
            self._batch_serialization.serialize_requests(requests),
        )
        logger.info(
            "queued pending batch {} ({} cards in {} chunk(s)) for Celery submit",
            batch.id,
            len(oracle_ids),
            len(records),
        )


async def _build_sweep_batch_requests(
    session: AsyncSession,
    tag_description: str,
    records: Sequence[SweepBatchRecord],
) -> list[Request]:
    """Build Anthropic batch items from chunk records (same CSV shape as historical submit path)."""
    all_oracle_ids = [oid for r in records for oid in r.oracle_ids]
    card_rows = await CardRepo().fetch_by_oracle_ids(session, all_oracle_ids)
    cards_by_oracle_id: dict[str, CardModel] = {c.oracle_id: c for c in card_rows}
    settings = get_settings()
    system_prompt = format_sweep_system_prompt(tag_description)
    return [
        Request(
            custom_id=record.custom_id,
            messages=[
                cards_to_csv(
                    [
                        cards_by_oracle_id[oid]
                        for oid in record.oracle_ids
                        if oid in cards_by_oracle_id
                    ]
                )
            ],
            model=settings.tag_sweep_model,
            max_tokens=settings.tag_sweep_max_tokens,
            system_prompt=system_prompt,
            output_schema_path=SWEEP_VERDICT_SCHEMA_PATH,
        )
        for record in records
    ]


def create_tag_sweep_initializer() -> TagSweepInitializer:
    """Wiring for CLI, Celery, and tests."""
    return TagSweepInitializer(
        sweep_repo=TagSweepRepo(),
        tag_repo=TagRepo(),
        audit_repo=TagAuditRepo(),
        batch_serialization=create_batch_serialization_service(),
    )
