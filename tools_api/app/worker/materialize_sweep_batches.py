"""Celery task: build pending sweep batch rows + payloads, then enqueue submit → poll pipeline."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import worker_session_scope
from app.log import configure_celery_worker_logging
from app.repository import TagSweepRepo
from app.services.tag_sweep_initializer import create_tag_sweep_initializer
from app.services.tag_sweep_service import create_tag_sweep_service

from .pipeline_task_names import PipelineTaskName
from .submit_batch import enqueue_submit_batches


def enqueue_materialize_sweep_batches(
    sweep_id: str,
    tag_name: str,
    *,
    limit: int,
    reenqueue_failed: bool,
) -> None:
    """Queue Celery to build outbox batches, then submit_batch → poll → process."""
    celery_app.send_task(
        PipelineTaskName.MATERIALIZE_SWEEP_BATCHES,
        kwargs={
            "sweep_id": sweep_id,
            "tag_name": tag_name,
            "limit": limit,
            "reenqueue_failed": reenqueue_failed,
        },
    )
    logger.info(
        "Enqueued materialize_sweep_batches for sweep {} (tag {!r}).",
        sweep_id,
        tag_name,
    )


@celery_app.task(bind=True, name=PipelineTaskName.MATERIALIZE_SWEEP_BATCHES)
def materialize_sweep_batches_worker(
    self: Any,
    sweep_id: str,
    tag_name: str,
    limit: int,
    reenqueue_failed: bool,
) -> None:
    configure_celery_worker_logging()
    sweep_uuid = uuid.UUID(sweep_id)

    async def _body() -> list[str]:
        init = create_tag_sweep_initializer()
        sweep_service = create_tag_sweep_service()
        sweep_repo = TagSweepRepo()
        async with worker_session_scope() as session:
            await init.materialize_sweep_batches(
                session,
                sweep_uuid,
                tag_name=tag_name,
                limit=limit,
                reenqueue_failed=reenqueue_failed,
            )
            sweep = await sweep_repo.get_sweep(session, sweep_uuid)
            if sweep is None:
                raise ValueError(f"Sweep {sweep_id} not found after materialize.")
            batch_ids = await sweep_service.get_pending_batch_ids_for_sweep(session, sweep)
            if not batch_ids:
                raise ValueError(f"No pending batches for sweep {sweep_id} after materialize.")
            return list(batch_ids)

    try:
        batch_ids = asyncio.run(_body())
    except Exception:
        logger.exception("materialize_sweep_batches failed for sweep {}", sweep_id)
        raise

    enqueue_submit_batches(batch_ids, PipelineTaskName.PROCESS_SWEEP_RUN)
    logger.info(
        "materialize_sweep_batches: sweep {} — enqueued submit for {} batch id(s)",
        sweep_id,
        len(batch_ids),
    )


__all__ = ["enqueue_materialize_sweep_batches", "materialize_sweep_batches_worker"]
