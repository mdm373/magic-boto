"""Celery task: submit audit batch after sweep, then enqueue audit poll/process pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.cmd.serve_celery import celery_app
from app.db import build_async_sqlalchemy_resources
from app.log import configure_celery_worker_logging
from app.services.tag_audit_initializer import create_tag_audit_initializer

from .pipeline_enqueue import enqueue_process_tag_audit
from .pipeline_task_names import INIT_TAG_AUDIT


@celery_app.task(bind=True, name=INIT_TAG_AUDIT)
def init_tag_audit_worker(
    self: Any,
    tag: str,
    audit_tagged_sample: int = 20,
    audit_excluded_sample: int = 40,
    audit_unsure_sample: int = 10,
) -> None:
    configure_celery_worker_logging()

    async def _body() -> None:
        resources = build_async_sqlalchemy_resources()
        async with resources.worker_session() as session:
            audit_id = await create_tag_audit_initializer().init_audit(
                session,
                tag,
                audit_tagged_sample,
                audit_excluded_sample,
                audit_unsure_sample,
            )
        enqueue_process_tag_audit(str(audit_id))

    try:
        asyncio.run(_body())
    except ValueError as e:
        logger.error("Sweep audit kickoff failed: {}", e)
        raise


__all__ = ["init_tag_audit_worker"]
