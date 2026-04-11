"""CLI entrypoint: delete batches whose status is at or before a pipeline ceiling."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import cli_session_scope
from app.models import batch_statuses_at_or_before, parse_batch_status
from app.repository.batch_repo import BatchRepo

_repo = BatchRepo()


async def _run(ceiling_raw: str) -> None:
    ceiling = parse_batch_status(ceiling_raw)
    statuses = batch_statuses_at_or_before(ceiling)
    status_values = ", ".join(sorted(s.value for s in statuses))
    logger.info(
        "Deleting batches with status in [{}] (ceiling={!r}, resolved to {}).",
        status_values,
        ceiling_raw,
        ceiling.value,
    )
    async with cli_session_scope() as session:
        n = await _repo.delete_batches_with_status_in(session, tuple(statuses))
    logger.info("Deleted {} batch row(s).", n)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Delete batches whose status is at or before the given pipeline status "
            "(inclusive). Default ceiling is PENDING_SUBMIT (outbox rows)."
        )
    )
    parser.add_argument(
        "--status",
        default="pending_submit",
        help=(
            "Ceiling batch status (inclusive), matching a BatchStatus member name "
            "case-insensitively (e.g. pending_submit, PENDING_SUBMIT, in_progress)."
        ),
    )
    args = parser.parse_args()
    try:
        asyncio.run(_run(args.status))
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
