"""Celery task registration for ``include=[\"app.worker.tasks\"]``.

Task bodies live in sibling modules; enqueue helpers next to each task send matching kwargs.
"""

from __future__ import annotations

from .init_tag_audit import init_tag_audit_worker
from .materialize_sweep_batches import materialize_sweep_batches_worker
from .poll_pipeline import poll_pipeline_worker
from .process_mtgjson_fetch import process_mtgjson_fetch_job_worker
from .process_sweep_run import process_sweep_run_worker
from .process_tag_audit import process_tag_audit_worker
from .submit_batch import submit_batch_worker

__all__ = [
    "init_tag_audit_worker",
    "materialize_sweep_batches_worker",
    "process_mtgjson_fetch_job_worker",
    "poll_pipeline_worker",
    "process_sweep_run_worker",
    "process_tag_audit_worker",
    "submit_batch_worker",
]
