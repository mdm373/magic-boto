"""Batch sweep kickoff — submit Anthropic batch requests for pending cards."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.repository import BatchChunkRecord, CardRepo, TagRepo, TagSweepRepo
from app.services import BatchApiClient, Request, cards_to_csv, create_batch_client
from settings import get_settings

_PROMPTS_DIR = Path("prompts/sweep")
_SYSTEM_PROMPT_TEMPLATE = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_OUTPUT_SCHEMA_PATH = Path("message_schema/sweep_verdict.json")


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


_card_repo = CardRepo()
_sweep_repo = TagSweepRepo()
_tag_repo = TagRepo()


async def _submit_chunks(
    run_id: uuid.UUID,
    oracle_ids: list[str],
    batch_client: BatchApiClient,
    system_prompt: str,
    output_schema_path: Path,
    label: str,
) -> None:
    """Chunk oracle_ids, fetch cards, submit one Anthropic batch, record in DB."""
    session_factory = get_async_session_factory()
    settings = get_settings()
    chunk_size = settings.tag_sweep_batch_size

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

    all_oracle_ids = [oid for record in records for oid in record.oracle_ids]
    async with session_factory() as session:
        cards_by_oracle_id = {
            c.oracle_id: c for c in await _card_repo.fetch_by_oracle_ids(session, all_oracle_ids)
        }

    requests = [
        Request(
            custom_id=record.custom_id,
            messages=[
                cards_to_csv(
                    [
                        cards_by_oracle_id[oid]
                        for oid in record.oracle_ids
                        if oid in cards_by_oracle_id
                    ]
                )
            ],
            model=settings.tag_sweep_model,
            max_tokens=settings.tag_sweep_max_tokens,
            system_prompt=system_prompt,
            output_schema_path=output_schema_path,
        )
        for record in records
    ]

    anthropic_batch_id = batch_client.submit_requests(requests)

    async with session_factory() as session:
        await _sweep_repo.record_batch_with_cards(
            session,
            run_id,
            anthropic_batch_id,
            records,
        )
        await session.commit()

    logger.info(
        "{}: submitted batch {} ({} cards in {} chunk(s))",
        label,
        anthropic_batch_id,
        len(oracle_ids),
        len(records),
    )


async def _run(tag_name: str, limit: int, reenqueue_failed: bool) -> uuid.UUID | None:
    settings = get_settings()
    session_factory = get_async_session_factory()

    async with session_factory() as session:
        tag = await _tag_repo.require_tag_model(session, tag_name)

    batch_client = create_batch_client()
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(tag_description=tag.description)
    logger.info("Using model: {}", settings.tag_sweep_model)

    async with session_factory() as session:
        run = await _sweep_repo.get_open_sweep(session, tag.id)
        if run is None:
            run = await _sweep_repo.create_sweep(session, tag.id)
            await session.commit()
            logger.info("Created new sweep run.")
        else:
            logger.info("Resuming existing run {}.", run.id)
        run_id: uuid.UUID = run.id

    logger.info("Run ID: {}", run_id)
    if reenqueue_failed:
        async with session_factory() as session:
            failed_ids = list(await _sweep_repo.get_failed_oracle_ids_for_sweep(session, run_id))
            if not failed_ids:
                logger.warning("Re-enqueue flagged for run with no failed ids")
                return run_id

            logger.info("Re-enqueueing {} failed oracle ID(s).", len(failed_ids))
        await _submit_chunks(
            run_id, failed_ids, batch_client, system_prompt, _OUTPUT_SCHEMA_PATH, "reenqueue"
        )
        return run_id

    async with session_factory() as session:
        tag_model = await _tag_repo.require_tag_model_by_id(
            session, tag.id, load_relationships=True
        )
        eligible = list(
            await _sweep_repo.fetch_eligible_oracle_ids(session, tag_model, run_id, limit=limit)
        )
        if not eligible:
            logger.info("No eligible cards to sweep")
            return run_id

        logger.info("{} eligible card(s) to submit.", len(eligible))
    await _submit_chunks(
        run_id, eligible, batch_client, system_prompt, _OUTPUT_SCHEMA_PATH, "kickoff"
    )
    return run_id


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    run_id = asyncio.run(_run(args.tag, args.limit, args.reenqueue_failed))
    if run_id is not None:
        print(run_id, flush=True)


if __name__ == "__main__":
    main()
