"""Batch sweep poll — check and update Anthropic batch statuses for a sweep run."""

from __future__ import annotations

import argparse
import asyncio
import time
import uuid
from collections.abc import Sequence

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.models.sweep_run_batch import SweepRunBatchModel
from app.services import create_sweep_run_service
from app.tag.batch.client import BatchSweepClient, create_batch_client

_POLL_INTERVAL_SECONDS = 30

_sweep_run_service = create_sweep_run_service()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll Anthropic batch status for a sweep run.")
    parser.add_argument("run_id", help="Sweep run UUID.")
    parser.add_argument(
        "--wait",
        action="store_true",
        default=False,
        help=f"Loop every {_POLL_INTERVAL_SECONDS}s until all batches reach a terminal state.",
    )
    return parser.parse_args()


async def _poll_once(
    run_id: uuid.UUID, batch_client: BatchSweepClient
) -> Sequence[SweepRunBatchModel]:
    """Fetch current batch statuses from Anthropic and persist them. Returns all batches."""
    session_factory = get_async_session_factory()

    # Poll only non-terminal batches.
    async with session_factory() as session:
        non_terminal = await _sweep_run_service.get_non_terminal_batches(session, run_id)

    for batch in non_terminal:
        batch_status = batch_client.get_batch_status(batch.batch_id)

        # Map Anthropic processing_status to our batch status.
        # 'in_progress' | 'canceling' → keep as-is; 'ended' → 'ended'
        new_status = batch_status.processing_status
        async with session_factory() as session:
            await _sweep_run_service.update_batch_status(
                session, batch.batch_id, new_status, batch_status.ended_at
            )
            await session.commit()

    # Return all batches with fresh statuses for display.
    async with session_factory() as session:
        return await _sweep_run_service.get_batches(session, run_id)


def _print_status_table(batches: list[SweepRunBatchModel]) -> None:
    header = f"{'batch_id':<30}  {'cards':>6}  {'status':<12}  completed_at"
    logger.info(header)
    logger.info("-" * len(header))
    for b in batches:
        completed = b.completed_at.strftime("%Y-%m-%d %H:%M") if b.completed_at else "—"
        logger.info(
            "{:<30}  {:>6}  {:<12}  {}",
            b.batch_id[:30],
            b.card_count,
            b.status,
            completed,
        )


async def _run(run_id_str: str, wait: bool) -> None:
    run_id = uuid.UUID(run_id_str)

    # Build the client without a tag description (not needed for status checks).
    batch_client = create_batch_client("")

    while True:
        batches = await _poll_once(run_id, batch_client)
        _print_status_table(batches)

        session_factory = get_async_session_factory()
        async with session_factory() as session:
            pending = await _sweep_run_service.get_non_terminal_batches(session, run_id)

        if not pending:
            logger.info("All batches are in a terminal state.")
            break

        if not wait:
            logger.info(
                "{} batch(es) still in progress. Re-run with --wait to poll automatically.",
                len(pending),
            )
            break

        logger.info(
            "{} batch(es) still in progress. Polling again in {}s...",
            len(pending),
            _POLL_INTERVAL_SECONDS,
        )
        time.sleep(_POLL_INTERVAL_SECONDS)


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    asyncio.run(_run(args.run_id, args.wait))


if __name__ == "__main__":
    main()
