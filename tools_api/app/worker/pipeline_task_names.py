"""Celery task name strings for tag pipelines.

These must match the ``name=`` argument on the corresponding ``@celery_app.task``
decorators (defined on modules re-exported from ``app.worker.tasks``).
"""

from __future__ import annotations

PROCESS_SWEEP_RUN = "app.worker.tasks.process_sweep_run"
INIT_TAG_AUDIT = "app.worker.tasks.init_tag_audit"
PROCESS_TAG_AUDIT = "app.worker.tasks.process_tag_audit"

__all__ = ["PROCESS_SWEEP_RUN", "INIT_TAG_AUDIT", "PROCESS_TAG_AUDIT"]
