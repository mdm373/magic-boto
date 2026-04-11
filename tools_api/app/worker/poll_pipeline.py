"""Pipeline poll: enqueue poll iterations and Celery task to sync batch status."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import worker_session_scope
from app.log import configure_celery_worker_logging
from app.services import BatchPollOutcome, create_batch_poller
from app.services.sweep_audit_poll_providers import create_fixed_batch_ids_poll_provider
from settings import get_settings

from .pipeline_task_names import PipelineTaskName, is_after_poll_target


def enqueue_poll_pipeline(
    after_poll: PipelineTaskName,
    batch_ids: Sequence[str],
    *,
    countdown: int | None = None,
) -> None:
    """Queue a poll iteration for the given batch IDs; on terminal, enqueue ``after_poll``."""
    if not is_after_poll_target(after_poll):
        raise ValueError(f"Invalid after_poll: {after_poll!r}")
    ids = list(batch_ids)
    if not ids:
        raise ValueError("batch_ids must be non-empty.")
    kwargs: dict[str, object] = {"after_poll": str(after_poll), "batch_ids": ids}
    if countdown is not None:
        celery_app.send_task(
            PipelineTaskName.POLL_PIPELINE,
            kwargs=kwargs,
            countdown=countdown,
        )
    else:
        celery_app.send_task(PipelineTaskName.POLL_PIPELINE, kwargs=kwargs)


@celery_app.task(bind=True, name=PipelineTaskName.POLL_PIPELINE)
def poll_pipeline_worker(self: Any, after_poll: str, batch_ids: list[str]) -> None:
    configure_celery_worker_logging()
    target = PipelineTaskName(after_poll)
    if not is_after_poll_target(target):
        raise ValueError(f"Invalid after_poll task name: {after_poll!r}")
    if not batch_ids:
        raise ValueError("batch_ids must be non-empty.")

    batch_uuids = tuple(uuid.UUID(b) for b in batch_ids)

    async def _body() -> None:
        batch_in_progress = False
        async with worker_session_scope() as session:
            poller = create_batch_poller(create_fixed_batch_ids_poll_provider(batch_uuids))
            poll = await poller.sync_with_anthropic(session)
            if poll.outcome == BatchPollOutcome.NO_BATCH_IDS:
                logger.info("Pipeline poll: no batch ids (unexpected) — skipping process.")
                return

            if poll.outcome == BatchPollOutcome.IN_PROGRESS:
                batch_in_progress = True

        if not batch_in_progress:
            celery_app.send_task(str(target), kwargs={"batch_ids": batch_ids})
            return

        countdown = get_settings().batch_poll_interval_seconds
        enqueue_poll_pipeline(target, batch_ids, countdown=countdown)
        return

    try:
        asyncio.run(_body())
    except ValueError as e:
        logger.error("Pipeline poll failed: {}", e)
        raise


__all__ = ["enqueue_poll_pipeline", "poll_pipeline_worker"]
