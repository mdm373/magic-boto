"""Celery task: run one MTGJSON fetch job (DB-tracked editions)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import worker_session_scope
from app.log import configure_celery_worker_logging
from app.services.mtgjson_fetch.worker_runner import run_mtgjson_fetch_job
from settings import get_settings

from .pipeline_task_names import PipelineTaskName


def enqueue_process_mtgjson_fetch_job(job_id: str) -> None:
    """Queue Celery to execute ``run_mtgjson_fetch_job`` for ``job_id``."""
    celery_app.send_task(
        PipelineTaskName.PROCESS_MTGJSON_FETCH_JOB,
        kwargs={"job_id": job_id},
    )
    logger.info("Enqueued MTGJSON fetch job {}.", job_id)


@celery_app.task(bind=True, name=PipelineTaskName.PROCESS_MTGJSON_FETCH_JOB)
def process_mtgjson_fetch_job_worker(self: Any, job_id: str) -> None:
    configure_celery_worker_logging()
    job_uuid = uuid.UUID(job_id)

    async def _body() -> None:
        settings = get_settings()
        async with worker_session_scope() as session:
            await run_mtgjson_fetch_job(session, job_id=job_uuid, settings=settings)

    try:
        asyncio.run(_body())
    except Exception:
        logger.exception("process_mtgjson_fetch_job_worker failed for job {}", job_id)
        raise


__all__ = ["enqueue_process_mtgjson_fetch_job", "process_mtgjson_fetch_job_worker"]
