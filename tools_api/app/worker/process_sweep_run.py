"""Celery task: poll sweep batches, apply sweep; optionally enqueue post-sweep audit kickoff."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import build_async_sqlalchemy_resources
from app.log import configure_celery_worker_logging
from app.services import (
    BatchPollOutcome,
    create_batch_poller,
    create_tag_sweep_processor,
)
from app.services.sweep_audit_poll_providers import create_sweep_poll_provider
from settings import get_settings

from .pipeline_enqueue import enqueue_init_tag_audit, enqueue_process_sweep_run
from .pipeline_task_names import PROCESS_SWEEP_RUN


@celery_app.task(bind=True, name=PROCESS_SWEEP_RUN)
def process_sweep_run_worker(
    self: Any,
    tag: str,
    include_unsure: bool = True,
    include_excluded: bool = True,
    audit_after: bool = False,
    audit_tagged_sample: int = 20,
    audit_excluded_sample: int = 40,
    audit_unsure_sample: int = 10,
) -> None:
    configure_celery_worker_logging()

    async def _body() -> None:
        resources = build_async_sqlalchemy_resources()
        reschedule_poll = False
        sweep_applied = False
        async with resources.worker_session() as session:
            poller = create_batch_poller(create_sweep_poll_provider(tag))
            poll = await poller.sync_with_anthropic(session)
            if poll.outcome == BatchPollOutcome.NO_BATCH_IDS:
                logger.info("Sweep pipeline: no batches for tag {!r} — nothing to process.", tag)
                return

            if poll.outcome == BatchPollOutcome.IN_PROGRESS:
                reschedule_poll = True
                return
            processor = create_tag_sweep_processor()
            await processor.run(session, tag, include_unsure, include_excluded)
            sweep_applied = True
        if reschedule_poll:
            enqueue_process_sweep_run(
                tag,
                include_unsure=include_unsure,
                include_excluded=include_excluded,
                audit_after=audit_after,
                audit_tagged_sample=audit_tagged_sample,
                audit_excluded_sample=audit_excluded_sample,
                audit_unsure_sample=audit_unsure_sample,
                countdown=get_settings().batch_poll_interval_seconds,
            )
        if audit_after and sweep_applied:
            enqueue_init_tag_audit(
                tag,
                audit_tagged_sample=audit_tagged_sample,
                audit_excluded_sample=audit_excluded_sample,
                audit_unsure_sample=audit_unsure_sample,
            )

    try:
        asyncio.run(_body())
    except ValueError as e:
        logger.error("Sweep pipeline failed: {}", e)
        raise


__all__ = ["process_sweep_run_worker"]
