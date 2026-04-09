"""Celery task: poll audit batch, then load results."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import build_async_sqlalchemy_resources
from app.log import configure_celery_worker_logging
from app.services import BatchPollOutcome, create_batch_poller, process_tag_audit
from app.services.sweep_audit_poll_providers import create_audit_poll_provider
from settings import get_settings

from .pipeline_enqueue import enqueue_process_tag_audit
from .pipeline_task_names import PROCESS_TAG_AUDIT


@celery_app.task(bind=True, name=PROCESS_TAG_AUDIT)
def process_tag_audit_worker(self: Any, audit_id: str) -> None:
    configure_celery_worker_logging()

    async def _body() -> None:
        resources = build_async_sqlalchemy_resources()
        reschedule_poll = False
        async with resources.worker_session() as session:
            poller = create_batch_poller(
                create_audit_poll_provider(uuid.UUID(audit_id)),
            )
            poll = await poller.sync_with_anthropic(session)
            if poll.outcome == BatchPollOutcome.NO_BATCH_IDS:
                logger.info("Audit pipeline: no batch for audit {} — nothing to process.", audit_id)
                return
            if poll.outcome == BatchPollOutcome.IN_PROGRESS:
                reschedule_poll = True
                return
            await process_tag_audit(session, audit_id, open_report=False)
        if reschedule_poll:
            countdown = get_settings().batch_poll_interval_seconds
            enqueue_process_tag_audit(audit_id, countdown=countdown)

    try:
        asyncio.run(_body())
    except ValueError as e:
        logger.error("Audit pipeline failed: {}", e)
        raise


__all__ = ["process_tag_audit_worker"]
