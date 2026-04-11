"""Celery task: submit audit batch for a pre-created audit row, then enqueue audit poll."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import worker_session_scope
from app.log import configure_celery_worker_logging
from app.services import create_tag_audit_init_service

from .pipeline_task_names import PipelineTaskName
from .submit_batch import enqueue_submit_batches


def enqueue_init_tag_audit(audit_id: str) -> None:
    """Queue audit batch kickoff for a pre-created audit row (outbox + submit → poll pipeline)."""
    celery_app.send_task(
        PipelineTaskName.INIT_TAG_AUDIT,
        kwargs={"audit_id": audit_id},
    )
    logger.info("Enqueued Celery init_tag_audit for audit {}.", audit_id)


@celery_app.task(bind=True, name=PipelineTaskName.INIT_TAG_AUDIT)
def init_tag_audit_worker(self: Any, audit_id: str) -> None:
    configure_celery_worker_logging()

    async def _body() -> None:
        init = create_tag_audit_init_service()
        async with worker_session_scope() as session:
            audit = await init.create_audit_batches(session, uuid.UUID(audit_id))
        enqueue_submit_batches([str(audit.batch_id)], PipelineTaskName.PROCESS_TAG_AUDIT)

    asyncio.run(_body())


__all__ = ["enqueue_init_tag_audit", "init_tag_audit_worker"]
