"""Shared logging configuration for CLI entrypoints and Celery workers."""

from __future__ import annotations

import os
import sys

from loguru import logger


def _configure_loguru_stderr_plain() -> None:
    """Single sink: stderr, plain ``{message}``, ``LOG_LEVEL`` env (default INFO)."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="{message}",
    )


def configure_cli_logging() -> None:
    """Route loguru to stderr with plain message format, respecting LOG_LEVEL."""
    _configure_loguru_stderr_plain()


def configure_celery_worker_logging() -> None:
    """Initialize loguru for Celery worker task runs (stderr, LOG_LEVEL).

    Call at the start of each task body so worker processes match CLI log behavior.
    """
    _configure_loguru_stderr_plain()
