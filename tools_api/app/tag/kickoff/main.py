"""Batch sweep kickoff — submit Anthropic batch requests for pending cards."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.models.magic_boto_card import MagicBotoCardModel
from app.models.magic_boto_tag import MagicBotoTagModel
from app.services import create_sweep_run_service, create_tag_service
from app.tag.batch.client import create_batch_client


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
            "re-run kickoff for the same tag to resume from the cursor. 0 = no limit."
        ),
    )
    parser.add_argument(
        "--oracle-ids-file",
        metavar="PATH",
        help="Submit only the oracle IDs listed in this file (one per line). "
        "Creates a new run; used to re-enqueue failed requests.",
    )
    return parser.parse_args()


_sweep_run_service = create_sweep_run_service()
_tag_service = create_tag_service()




async def _submit_oracle_ids_file(oracle_ids_file: str, tag: MagicBotoTagModel) -> None:
    """Create a fresh run and submit the oracle IDs from the file."""
    oracle_ids = [
        line.strip() for line in Path(oracle_ids_file).read_text().splitlines() if line.strip()
    ]
    if not oracle_ids:
        logger.warning("No oracle IDs found in '{}'; nothing to submit.", oracle_ids_file)
        return

    session_factory = get_async_session_factory()
    batch_client = create_batch_client(tag.description)

    # Create the run.
    async with session_factory() as session:
        run = await _sweep_run_service.create_run(session, tag.id)
        await session.commit()
        run_id = run.id

    # Fetch the cards.
    async with session_factory() as session:
        cards = await _sweep_run_service.fetch_cards_by_oracle_ids(session, oracle_ids)

    if not cards:
        logger.warning("None of the provided oracle IDs matched known cards.")
        return

    logger.info("Re-enqueueing {} card(s) from '{}'.", len(cards), oracle_ids_file)

    # Submit in chunks, committing each batch atomically.
    for i in range(0, len(cards), batch_client.max_requests_per_batch):
        chunk = cards[i : i + batch_client.max_requests_per_batch]
        batch_id = batch_client.submit_batch(chunk)
        async with session_factory() as session:
            await _sweep_run_service.record_batch(
                session, run_id, batch_id, len(chunk), str(chunk[-1].oracle_id)
            )
            await session.commit()
        logger.info("  submitted batch {} ({} cards)", batch_id, len(chunk))

    # All cards queued — mark the run accordingly.
    async with session_factory() as session:
        await _sweep_run_service.mark_all_cards_queued(session, run_id)
        await session.commit()

    logger.info("Run ID: {}", run_id)


async def _run(tag_name: str, limit: int, oracle_ids_file: str | None) -> uuid.UUID | None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        tag = await _tag_service.require_tag_model(session, tag_name)

    if oracle_ids_file is not None:
        await _submit_oracle_ids_file(oracle_ids_file, tag)
        return None

    batch_client = create_batch_client(tag.description)

    # Get or create the open run for this tag.
    async with session_factory() as session:
        run = await _sweep_run_service.get_open_run(session, tag.id)
        if run is None:
            run = await _sweep_run_service.create_run(session, tag.id)
            await session.commit()
            logger.info("Created new sweep run.")
        else:
            logger.info(
                "Resuming existing run {} (cursor: {}).",
                run.id,
                run.last_submitted_oracle_id or "start",
            )
        run_id: uuid.UUID = run.id
        cursor: str | None = run.last_submitted_oracle_id

    # Derive the epoch gate from the last complete run.
    async with session_factory() as session:
        last_swept_at = await _sweep_run_service.get_epoch_gate(session, tag.id)

    remaining = limit if limit > 0 else None
    total_submitted = 0

    while True:
        max_per_batch = batch_client.max_requests_per_batch
        chunk_size = min(max_per_batch, remaining) if remaining is not None else max_per_batch

        # Load the tag model fresh each iteration (selectin relationships).
        async with session_factory() as session:
            tag_model = await _tag_service.require_tag_model_by_id(
                session, tag.id, load_relationships=True
            )

        async with session_factory() as session:
            cards: list[MagicBotoCardModel] = await _sweep_run_service.fetch_all_pending(
                session, tag_model, last_swept_at, cursor, chunk_size
            )

        if not cards:
            # All eligible cards for this epoch have been submitted.
            async with session_factory() as session:
                await _sweep_run_service.mark_all_cards_queued(session, run_id)
                await session.commit()
            logger.info(
                "All cards queued. {} card(s) submitted this call. Run ID: {}",
                total_submitted,
                run_id,
            )
            break

        # Submit to Anthropic — synchronous, blocks until confirmed.
        batch_id = batch_client.submit_batch(cards)

        # Commit the batch record and advance the cursor atomically.
        async with session_factory() as session:
            await _sweep_run_service.record_batch(
                session, run_id, batch_id, len(cards), str(cards[-1].oracle_id)
            )
            await session.commit()

        cursor = str(cards[-1].oracle_id)
        total_submitted += len(cards)

        logger.info(
            "Submitted batch {} ({} cards | cursor: {})",
            batch_id,
            len(cards),
            cursor,
        )

        if remaining is not None:
            remaining -= len(cards)
            if remaining <= 0:
                logger.info(
                    "Limit reached. {} card(s) submitted. Run stays open. Run ID: {}",
                    total_submitted,
                    run_id,
                )
                break

    logger.info("Run ID: {}", run_id)
    return run_id


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    run_id = asyncio.run(_run(args.tag, args.limit, args.oracle_ids_file))
    if run_id is not None:
        print(run_id, flush=True)


if __name__ == "__main__":
    main()
