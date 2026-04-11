"""Audit pipeline: enqueue poll-only runs and Celery task to load batch results."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import worker_session_scope
from app.log import configure_celery_worker_logging
from app.repository import TagAuditRepo
from app.services import create_tag_audit_processing_service, create_tag_audit_service

from .pipeline_task_names import PipelineTaskName
from .poll_pipeline import enqueue_poll_pipeline


async def _audit_poll_batch_ids(audit_id: str) -> list[str]:
    async with worker_session_scope() as session:
        audit = await TagAuditRepo().get_audit(session, uuid.UUID(audit_id))
        if audit is None:
            raise ValueError(f"Audit {audit_id} not found.")
        if audit.batch_id is None:
            raise ValueError(f"Audit {audit_id} has no batch — run kickoff first.")
        return [str(audit.batch_id)]


def enqueue_process_audit_polling(
    audit_id: str,
    *,
    countdown: int | None = None,
) -> None:
    """Resolve the audit's batch id and queue poll until terminal, then process."""
    batch_ids = asyncio.run(_audit_poll_batch_ids(audit_id))
    if countdown is not None:
        enqueue_poll_pipeline(
            PipelineTaskName.PROCESS_TAG_AUDIT,
            batch_ids,
            countdown=countdown,
        )
        logger.info(
            "Enqueued Celery audit pipeline poll for audit {} (scheduled in {}s).",
            audit_id,
            countdown,
        )
    else:
        enqueue_poll_pipeline(PipelineTaskName.PROCESS_TAG_AUDIT, batch_ids)
        logger.info("Enqueued Celery audit pipeline poll for audit {}.", audit_id)


@celery_app.task(bind=True, name=PipelineTaskName.PROCESS_TAG_AUDIT)
def process_tag_audit_worker(self: Any, batch_ids: list[str]) -> None:
    configure_celery_worker_logging()
    if not batch_ids:
        raise ValueError("batch_ids must be non-empty.")

    proc = create_tag_audit_processing_service()
    audit_service = create_tag_audit_service()

    async def _body() -> None:
        uuids = [uuid.UUID(b) for b in batch_ids]
        async with worker_session_scope() as session:
            audit_id = await audit_service.require_single_audit_id_for_batch_ids(session, uuids)
            await proc.run(session, str(audit_id))

    try:
        asyncio.run(_body())
    except ValueError as e:
        logger.error("Audit pipeline failed: {}", e)
        raise


__all__ = ["enqueue_process_audit_polling", "process_tag_audit_worker"]
