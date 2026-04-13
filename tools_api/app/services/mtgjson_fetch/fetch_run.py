"""Shared MTGJSON fetch entry (CLI + MCP): parse args and run the ingest job."""

from __future__ import annotations

import re
from collections.abc import Sequence

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from settings import Settings

from .fetch_job import create_mtgjson_fetch_job

_ALWAYS_REFRESH_PATTERN = re.compile(r"^[A-Za-z0-9,-]+$")


def parse_always_refresh_set_codes(arg: str) -> frozenset[str]:
    """Parse a comma-separated ``--always-refresh`` value into uppercased set codes."""
    raw = arg.strip()
    if raw and _ALWAYS_REFRESH_PATTERN.fullmatch(raw) is None:
        raise ValueError(
            "--always-refresh must be comma-separated letters, digits, or hyphens only."
        )
    return frozenset(p.strip().upper() for p in raw.split(",") if p.strip())


async def execute_mtgjson_fetch(
    session: AsyncSession,
    *,
    settings: Settings,
    always_refresh_set_codes: frozenset[str],
) -> tuple[str, ...]:
    """Run MTGJSON ingest; returns set codes whose per-set JSON was downloaded (not cache hit)."""
    job = create_mtgjson_fetch_job(
        session=session,
        settings=settings,
        always_refresh_set_codes=always_refresh_set_codes,
    )
    downloaded = await job.run()
    return tuple(sorted(set(downloaded)))


def log_cli_fetch_result(sets_downloaded: Sequence[str]) -> None:
    """Log fetch outcome for the CLI (structured line for operators)."""
    if sets_downloaded:
        logger.info("sets_downloaded: {}", ", ".join(sets_downloaded))
    else:
        logger.info("sets_downloaded: (none)")
