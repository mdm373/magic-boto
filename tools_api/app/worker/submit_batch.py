"""Outbox submit: enqueue submit task and Celery worker (then chain poll)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import worker_session_scope
from app.log import configure_celery_worker_logging
from app.models import BatchStatus
from app.repository import BatchRepo
from app.services.batch_submit import create_batch_submit_service

from .pipeline_task_names import PipelineTaskName, is_after_poll_target
from .poll_pipeline import enqueue_poll_pipeline


def enqueue_submit_batches(
    batch_ids: Sequence[str],
    after_poll: PipelineTaskName,
) -> None:
    """Queue Anthropic submit for each id (skips non-``pending_submit``); then poll all ids."""
    if not is_after_poll_target(after_poll):
        raise ValueError(f"Invalid after_poll for submit_batches: {after_poll!r}")
    ids = list(batch_ids)
    if not ids:
        raise ValueError("batch_ids must be non-empty.")
    celery_app.send_task(
        PipelineTaskName.SUBMIT_BATCH,
        kwargs={"batch_ids": ids, "after_poll": str(after_poll)},
    )
    logger.info(
        "Enqueued Celery submit_batches for {} batch id(s)",
        len(ids),
    )


@celery_app.task(bind=True, name=PipelineTaskName.SUBMIT_BATCH)
def submit_batch_worker(self: Any, batch_ids: list[str], after_poll: str) -> None:
    configure_celery_worker_logging()
    target = PipelineTaskName(after_poll)
    if not is_after_poll_target(target):
        raise ValueError(f"Invalid after_poll task name: {after_poll!r}")
    if not batch_ids:
        raise ValueError("batch_ids must be non-empty.")
    batch_submit_service = create_batch_submit_service()

    async def _body() -> bool:
        batch_repo = BatchRepo()
        for batch_id in (uuid.UUID(bid) for bid in batch_ids):
            async with worker_session_scope() as session:
                batch = await batch_repo.get_batch(session, batch_id)
            if batch is None:
                raise ValueError(f"Batch {batch_id} not found.")
            if batch.status != BatchStatus.PENDING_SUBMIT:
                logger.info("Batch {} is {}, skipping submit.", batch_id, batch.status)
                continue

            # Own commit per batch: once Anthropic accepts a batch its ID must be persisted
            # before the next submit, or a later failure orphans it (billed, never processed).
            try:
                result = await batch_submit_service.submit_to_anthropic(batch)
                async with worker_session_scope() as session:
                    await batch_repo.apply_outbox_anthropic_batch_id(
                        session, result.batch_uuid, result.anthropic_batch_id
                    )
            except Exception:
                logger.exception("failure during batch submission, possibly orphaned: {}", batch_id)
                return False
        return True

    success = asyncio.run(_body())
    if not success:
        logger.error(
            "task will complete to avoid retrying to anthropic. resolution/resubmit required"
        )
        return

    enqueue_poll_pipeline(target, batch_ids)
    logger.info(
        "submit_batch: finished outbox submit for {} batch id(s) — enqueued poll → {}",
        len(batch_ids),
        target,
    )


__all__ = ["enqueue_submit_batches", "submit_batch_worker"]
