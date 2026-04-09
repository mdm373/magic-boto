"""Celery application for tag sweep/audit pipeline workers.

Use ``celery -A app.cmd.serve_celery`` (or ``:celery_app`` explicitly).
"""

from __future__ import annotations

from celery import Celery

from settings import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    redis_url = settings.celery_redis_url
    celery = Celery(
        "magic_boto_tools",
        broker=redis_url,
        backend=redis_url,
        include=["app.worker.tasks"],
    )
    celery.conf.update(
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
    )
    return celery


celery_app = create_celery_app()

__all__ = ["celery_app", "create_celery_app"]
