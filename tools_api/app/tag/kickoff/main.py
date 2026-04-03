"""Batch sweep kickoff — submit Anthropic batch requests for pending cards."""

from __future__ import annotations

import argparse
import asyncio
import uuid

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.services import create_sweep_run_service, create_tag_service
from app.tag.batch.client import BatchChunk, BatchChunkRecord, BatchSweepClient, create_batch_client
from settings import get_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit batch sweep requests for a tag.")
    parser.add_argument("tag", help="Tag name to sweep (must already exist).")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Submit at most N cards then exit. The run stays open; "
            "re-run kickoff for the same tag to resume. 0 = no limit."
        ),
    )
    parser.add_argument(
        "--reenqueue-failed",
        action="store_true",
        default=False,
        help="Re-submit oracle IDs from failed batches in the current open run.",
    )
    return parser.parse_args()


_sweep_run_service = create_sweep_run_service()
_tag_service = create_tag_service()


async def _submit_chunks(
    run_id: uuid.UUID,
    oracle_ids: list[str],
    batch_client: BatchSweepClient,
    chunk_size: int,
    label: str,
) -> None:
    """Chunk oracle_ids, fetch cards, submit one Anthropic batch, record in DB."""
    session_factory = get_async_session_factory()
    settings = get_settings()

    records: list[BatchChunkRecord] = [
        BatchChunkRecord(
            custom_id=f"chunk_{i // chunk_size}",
            oracle_ids=oracle_ids[i : i + chunk_size],
        )
        for i in range(0, len(oracle_ids), chunk_size)
    ]

    if len(records) > settings.batch_api_max_requests:
        raise RuntimeError(
            f"Chunk count {len(records)} exceeds batch_api_max_requests "
            f"({settings.batch_api_max_requests}). Reduce --limit or increase chunk size."
        )

    # Fetch card models for all chunks.
    all_oracle_ids = [oid for record in records for oid in record.oracle_ids]
    async with session_factory() as session:
        cards_by_oracle_id = {
            c.oracle_id: c
            for c in await _sweep_run_service.fetch_cards_by_oracle_ids(session, all_oracle_ids)
        }

    chunks: list[BatchChunk] = [
        BatchChunk(
            custom_id=record.custom_id,
            cards=[
                cards_by_oracle_id[oid]
                for oid in record.oracle_ids
                if oid in cards_by_oracle_id
            ],
        )
        for record in records
    ]

    batch_id = batch_client.submit_batch(chunks)

    async with session_factory() as session:
        await _sweep_run_service.record_batch_with_cards(
            session,
            run_id,
            batch_id,
            records,
        )
        await session.commit()

    logger.info(
        "{}: submitted batch {} ({} cards in {} chunk(s))",
        label,
        batch_id,
        len(oracle_ids),
        len(records),
    )


async def _run(tag_name: str, limit: int, reenqueue_failed: bool) -> uuid.UUID | None:
    settings = get_settings()
    session_factory = get_async_session_factory()

    async with session_factory() as session:
        tag = await _tag_service.require_tag_model(session, tag_name)

    batch_client = create_batch_client(tag.description)
    logger.info("Using model: {}", settings.tag_sweep_model)

    # Get or create the open run for this tag.
    async with session_factory() as session:
        run = await _sweep_run_service.get_open_run(session, tag.id)
        if run is None:
            run = await _sweep_run_service.create_run(session, tag.id)
            await session.commit()
            logger.info("Created new sweep run.")
        else:
            logger.info("Resuming existing run {}.", run.id)
        run_id: uuid.UUID = run.id

    if reenqueue_failed:
        async with session_factory() as session:
            failed_ids = list(
                await _sweep_run_service.get_failed_oracle_ids_for_run(session, run_id)
            )
        if not failed_ids:
            logger.info("No failed oracle IDs found for run {}.", run_id)
        else:
            logger.info("Re-enqueueing {} failed oracle ID(s).", len(failed_ids))
            await _submit_chunks(
                run_id, failed_ids, batch_client, settings.tag_sweep_batch_size, "reenqueue"
            )
        logger.info("Run ID: {}", run_id)
        return run_id

    # Load tag model with relationships for eligibility filtering.
    async with session_factory() as session:
        tag_model = await _tag_service.require_tag_model_by_id(
            session, tag.id, load_relationships=True
        )

    async with session_factory() as session:
        eligible = list(
            await _sweep_run_service.fetch_eligible_oracle_ids(
                session, tag_model, run_id, limit=limit
            )
        )

    if not eligible:
        logger.info("No eligible cards to sweep for run {}.", run_id)
        logger.info("Run ID: {}", run_id)
        return run_id

    logger.info("{} eligible card(s) to submit.", len(eligible))
    await _submit_chunks(run_id, eligible, batch_client, settings.tag_sweep_batch_size, "kickoff")

    logger.info("Run ID: {}", run_id)
    return run_id


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    run_id = asyncio.run(_run(args.tag, args.limit, args.reenqueue_failed))
    if run_id is not None:
        print(run_id, flush=True)


if __name__ == "__main__":
    main()
