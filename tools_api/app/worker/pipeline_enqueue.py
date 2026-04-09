"""Enqueue tag sweep / audit Celery pipelines by registered task name.

This is the only module (besides ``app.cmd.serve_celery``) that should import
``celery_app`` for sending work. Callers should use the package barrel
(``enqueue_process_sweep_run``, ``enqueue_process_tag_audit``,
``enqueue_sweep_audit_kickoff``) — not task objects from ``tasks``, avoiding import cycles.
"""

from __future__ import annotations

from loguru import logger

from app.cmd.serve_celery import celery_app

from .pipeline_task_names import (
    INIT_TAG_AUDIT,
    PROCESS_SWEEP_RUN,
    PROCESS_TAG_AUDIT,
)


def enqueue_process_sweep_run(
    tag: str,
    *,
    include_unsure: bool = True,
    include_excluded: bool = True,
    audit_after: bool = False,
    audit_tagged_sample: int = 20,
    audit_excluded_sample: int = 40,
    audit_unsure_sample: int = 10,
    countdown: int | None = None,
) -> None:
    """Queue the sweep pipeline task (poll until terminal, then process sweep).

    If ``audit_after`` is true, a separate ``process_sweep_audit_kickoff`` task is
    enqueued after sweep succeeds (distinct checkpoint from sweep processing).
    """
    kwargs = {
        "tag": tag,
        "include_unsure": include_unsure,
        "include_excluded": include_excluded,
        "audit_after": audit_after,
        "audit_tagged_sample": audit_tagged_sample,
        "audit_excluded_sample": audit_excluded_sample,
        "audit_unsure_sample": audit_unsure_sample,
    }
    if countdown is not None:
        celery_app.send_task(PROCESS_SWEEP_RUN, kwargs=kwargs, countdown=countdown)
        logger.info(
            "Enqueued Celery sweep pipeline for tag {!r} (scheduled in {}s).",
            tag,
            countdown,
        )
    else:
        celery_app.send_task(PROCESS_SWEEP_RUN, kwargs=kwargs)
        logger.info("Enqueued Celery sweep pipeline for tag {!r}.", tag)


def enqueue_process_tag_audit(
    audit_id: str,
    *,
    countdown: int | None = None,
) -> None:
    """Queue the audit pipeline task (poll until terminal, then process)."""
    kwargs = {"audit_id": audit_id}
    if countdown is not None:
        celery_app.send_task(PROCESS_TAG_AUDIT, kwargs=kwargs, countdown=countdown)
        logger.info(
            "Enqueued Celery audit pipeline for audit {} (scheduled in {}s).",
            audit_id,
            countdown,
        )
    else:
        celery_app.send_task(PROCESS_TAG_AUDIT, kwargs=kwargs)
        logger.info("Enqueued Celery audit pipeline for audit {}.", audit_id)


def enqueue_init_tag_audit(
    tag: str,
    *,
    audit_tagged_sample: int = 20,
    audit_excluded_sample: int = 40,
    audit_unsure_sample: int = 10,
) -> None:
    """Queue audit batch kickoff after sweep completed (separate Celery task from sweep)."""
    celery_app.send_task(
        INIT_TAG_AUDIT,
        kwargs={
            "tag": tag,
            "audit_tagged_sample": audit_tagged_sample,
            "audit_excluded_sample": audit_excluded_sample,
            "audit_unsure_sample": audit_unsure_sample,
        },
    )
    logger.info("Enqueued Celery sweep audit kickoff for tag {!r}.", tag)


__all__ = [
    "enqueue_process_sweep_run",
    "enqueue_process_tag_audit",
    "enqueue_init_tag_audit",
]
