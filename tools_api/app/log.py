"""Shared logging configuration for CLI entrypoints."""

from __future__ import annotations

import os
import sys

from loguru import logger


def configure_cli_logging() -> None:
    """Route loguru to stderr with plain message format, respecting LOG_LEVEL."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="{message}",
    )
