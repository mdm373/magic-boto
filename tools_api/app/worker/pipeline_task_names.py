"""Registered Celery task name strings — must match ``name=`` on task decorators.

Use :class:`PipelineTaskName` members with ``send_task`` and ``@celery_app.task``.
"""

from __future__ import annotations

from enum import StrEnum


class PipelineTaskName(StrEnum):
    """Full Celery task names (``app.worker.tasks.<function>``)."""

    MATERIALIZE_SWEEP_BATCHES = "app.worker.tasks.materialize_sweep_batches"
    POLL_PIPELINE = "app.worker.tasks.poll_pipeline"
    PROCESS_SWEEP_RUN = "app.worker.tasks.process_sweep_run"
    INIT_TAG_AUDIT = "app.worker.tasks.init_tag_audit"
    PROCESS_TAG_AUDIT = "app.worker.tasks.process_tag_audit"
    PROCESS_MTGJSON_FETCH_JOB = "app.worker.tasks.process_mtgjson_fetch_job"
    SUBMIT_BATCH = "app.worker.tasks.submit_batch"


_AFTER_POLL_TARGETS: frozenset[PipelineTaskName] = frozenset(
    {
        PipelineTaskName.PROCESS_SWEEP_RUN,
        PipelineTaskName.PROCESS_TAG_AUDIT,
    },
)


def is_after_poll_target(name: PipelineTaskName) -> bool:
    """Return True if ``name`` is a valid ``after_poll`` for :func:`poll_pipeline_worker`."""
    return name in _AFTER_POLL_TARGETS


__all__ = [
    "PipelineTaskName",
    "is_after_poll_target",
]
