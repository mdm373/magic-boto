"""Celery task registration for ``include=[\"app.worker.tasks\"]``.

Task bodies live in sibling modules; ``pipeline_enqueue`` sends flat kwargs that
match each worker's parameters.
"""

from __future__ import annotations

from .init_tag_audit import init_tag_audit_worker
from .process_sweep_run import process_sweep_run_worker
from .process_tag_audit import process_tag_audit_worker

__all__ = [
    "init_tag_audit_worker",
    "process_sweep_run_worker",
    "process_tag_audit_worker",
]
