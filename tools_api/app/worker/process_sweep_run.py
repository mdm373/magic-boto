"""Sweep pipeline: enqueue poll-only runs and Celery task to apply batch results."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import worker_session_scope
from app.log import configure_celery_worker_logging
from app.repository import TagRepo
from app.services import create_tag_sweep_processor, create_tag_sweep_service

from .init_tag_audit import enqueue_init_tag_audit
from .pipeline_task_names import PipelineTaskName
from .poll_pipeline import enqueue_poll_pipeline


def enqueue_process_sweep_polling(
    batch_ids: Sequence[str],
    *,
    countdown: int | None = None,
) -> None:
    """Queue poll until batches are terminal, then ``process_sweep_run_worker``."""
    if not batch_ids:
        raise ValueError("batch_ids must be non-empty.")

    if countdown is not None:
        enqueue_poll_pipeline(PipelineTaskName.PROCESS_SWEEP_RUN, batch_ids, countdown=countdown)
    else:
        enqueue_poll_pipeline(PipelineTaskName.PROCESS_SWEEP_RUN, batch_ids)
    logger.info("Enqueued sweep poll for {} in {}s).", len(batch_ids), countdown or 0)


@celery_app.task(bind=True, name=PipelineTaskName.PROCESS_SWEEP_RUN)
def process_sweep_run_worker(self: Any, batch_ids: list[str]) -> None:
    configure_celery_worker_logging()
    if not batch_ids:
        raise ValueError("batch_ids must be non-empty.")

    async def _body() -> None:
        uuids = [uuid.UUID(b) for b in batch_ids]
        sweep_service = create_tag_sweep_service()
        tag_repo = TagRepo()
        processor = create_tag_sweep_processor()
        async with worker_session_scope() as session:
            sweep = await sweep_service.require_open_sweep_for_batch_ids(session, uuids)
            tag_row = await tag_repo.require_tag_model_by_id(session, sweep.tag_id)
            tag_name = tag_row.name
            include_unsure = sweep.pipeline_include_unsure
            include_excluded = sweep.pipeline_include_excluded
            post_audit_id = sweep.post_sweep_audit_id
            await processor.run(session, tag_name, include_unsure, include_excluded)
        if post_audit_id is not None:
            enqueue_init_tag_audit(str(post_audit_id))

    try:
        asyncio.run(_body())
    except ValueError as e:
        logger.error("Sweep pipeline failed: {}", e)
        raise


__all__ = ["enqueue_process_sweep_polling", "process_sweep_run_worker"]
