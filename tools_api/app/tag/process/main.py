"""Batch sweep process — apply tags from completed Anthropic batch results."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.models.sweep_run_batch import SweepRunBatchModel
from app.services import create_sweep_run_service, create_tag_service
from app.services.tag_service import CardTagEntry
from app.tag.batch.client import BatchSweepClient, create_batch_client
from app.tag.batch.verdict import Verdict

_sweep_run_service = create_sweep_run_service()
_tag_service = create_tag_service()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply tags from completed batch results for a sweep run."
    )
    parser.add_argument("run_id", help="Sweep run UUID.")
    parser.add_argument(
        "--include-unsure",
        action="store_true",
        default=False,
        help="Tag uncertain cards with {tag}_unsure.",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        default=False,
        help="Tag non-qualifying cards with {tag}_excluded.",
    )
    return parser.parse_args()



def _parse_verdicts(text: str, expected: int) -> dict[int, Verdict]:
    """Parse structured JSON verdicts from the response.

    Returns a dict of row index → Verdict for valid, non-duplicate entries within range.
    Rows absent from the dict (missing, duplicate, or unparseable) should be failed.
    """
    char_map = {"Y": Verdict.TAG, "N": Verdict.EXCLUDE, "U": Verdict.UNSURE}
    try:
        items = json.loads(text)["verdicts"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}

    seen: dict[int, Verdict] = {}
    duplicates: set[int] = set()
    for item in items:
        try:
            row = int(item["r"])
            verdict = char_map[str(item["v"]).upper()]
        except (KeyError, TypeError, ValueError):
            continue
        if row < 0 or row >= expected:
            continue
        if row in seen:
            duplicates.add(row)
        else:
            seen[row] = verdict

    for row in duplicates:
        del seen[row]

    return seen


async def _ensure_side_tags(tag_name: str, include_unsure: bool, include_excluded: bool) -> None:
    """Create _unsure / _excluded side-tags if they are needed and don't yet exist."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        if include_unsure and await _tag_service.get_tag(session, f"{tag_name}_unsure") is None:
            await _tag_service.create_tag(
                session,
                f"{tag_name}_unsure",
                f"Cards flagged for manual review during the '{tag_name}' tag sweep.",
            )
            logger.info("Created tag '{}_unsure'.", tag_name)
        if include_excluded and await _tag_service.get_tag(session, f"{tag_name}_excluded") is None:
            await _tag_service.create_tag(
                session,
                f"{tag_name}_excluded",
                f"Cards that do not qualify for '{tag_name}', as determined by the tag sweep.",
            )
            logger.info("Created tag '{}_excluded'.", tag_name)
        await session.commit()


@dataclass(frozen=True, slots=True)
class _BatchClassification:
    tag_entries: Sequence[CardTagEntry] = field(default_factory=list)
    unsure_entries: Sequence[CardTagEntry] = field(default_factory=list)
    excluded_entries: Sequence[CardTagEntry] = field(default_factory=list)
    failed_ids: Sequence[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


async def _classify_batch_results(
    batch_client: BatchSweepClient, batch: SweepRunBatchModel
) -> _BatchClassification:
    """Stream batch results and sort each chunk into tag / unsure / excluded / failed buckets."""
    session_factory = get_async_session_factory()
    tag_entries: list[CardTagEntry] = []
    unsure_entries: list[CardTagEntry] = []
    excluded_entries: list[CardTagEntry] = []
    failed_ids: list[str] = []
    input_tokens = output_tokens = cache_read_tokens = cache_creation_tokens = 0

    for result in batch_client.get_results(batch.batch_id):
        chunk_custom_id: str = result.custom_id

        if result.result.type != "succeeded":
            logger.warning(
                "Chunk {} in batch {} failed with type '{}'.",
                chunk_custom_id,
                batch.batch_id,
                result.result.type,
            )
            # Mark all cards in this chunk as failed.
            async with session_factory() as session:
                chunk_cards = await _sweep_run_service.get_batch_cards(
                    session, batch.id, chunk_custom_id
                )
            failed_ids.extend(c.oracle_id for c in chunk_cards)
            continue

        usage = result.result.message.usage
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0

        text_blocks: list[Any] = [b for b in result.result.message.content if b.type == "text"]
        raw = text_blocks[0].text if text_blocks else ""

        async with session_factory() as session:
            chunk_cards = await _sweep_run_service.get_batch_cards(
                session, batch.id, chunk_custom_id
            )

        verdicts = _parse_verdicts(raw, expected=len(chunk_cards))

        missing = len(chunk_cards) - len(verdicts)
        if missing > 0:
            logger.warning(
                "Chunk {} in batch {}: {} of {} verdicts missing — failing those cards.",
                chunk_custom_id,
                batch.batch_id,
                missing,
                len(chunk_cards),
            )

        for i, card_row in enumerate(chunk_cards):
            verdict = verdicts.get(i)
            if verdict is None:
                failed_ids.append(card_row.oracle_id)
                continue
            entry = CardTagEntry(oracle_id=card_row.oracle_id, reason=None)
            match verdict:
                case Verdict.TAG:
                    tag_entries.append(entry)
                case Verdict.UNSURE:
                    unsure_entries.append(entry)
                case _:
                    excluded_entries.append(entry)

    return _BatchClassification(
        tag_entries=tag_entries,
        unsure_entries=unsure_entries,
        excluded_entries=excluded_entries,
        failed_ids=failed_ids,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )


async def _apply_batch(
    batch: SweepRunBatchModel,
    classified: _BatchClassification,
    tag_name: str,
    include_unsure: bool,
    include_excluded: bool,
) -> None:
    """Persist tag assignments for one batch and mark it processed."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        if classified.tag_entries:
            await _tag_service.add_card_tags(session, tag_name, classified.tag_entries)
        if include_unsure and classified.unsure_entries:
            await _tag_service.add_card_tags(
                session, f"{tag_name}_unsure", classified.unsure_entries
            )
        if include_excluded and classified.excluded_entries:
            await _tag_service.add_card_tags(
                session, f"{tag_name}_excluded", classified.excluded_entries
            )
        if classified.failed_ids:
            await _sweep_run_service.mark_batch_cards_failed(
                session, batch.id, classified.failed_ids
            )
        await _sweep_run_service.mark_batch_processed(session, batch.batch_id)
        await session.commit()


async def _maybe_complete_run(run_id: uuid.UUID, tag: Any) -> None:
    """Mark the run complete when all batches are processed and no eligible cards remain."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        complete = await _sweep_run_service.is_run_complete(session, run_id, tag)
        if complete:
            await _sweep_run_service.complete_run(session, run_id)
            await session.commit()
            logger.info("Run {} marked complete.", run_id)
        else:
            remaining = await _sweep_run_service.get_non_terminal_batches(session, run_id)
            eligible = await _sweep_run_service.fetch_eligible_oracle_ids(session, tag, run_id)
            logger.info(
                "Run {} remains open ({} batch(es) not yet processed, "
                "{} eligible card(s) remaining).",
                run_id,
                len(remaining),
                len(eligible),
            )


async def _run(run_id_str: str, include_unsure: bool, include_excluded: bool) -> None:
    run_id = uuid.UUID(run_id_str)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        run = await _sweep_run_service.get_run(session, run_id)
        if run is None:
            raise ValueError(f"Sweep run {run_id} not found.")
        tag = await _tag_service.require_tag_model_by_id(
            session, run.tag_id, load_relationships=True
        )

    await _ensure_side_tags(tag.name, include_unsure, include_excluded)

    async with session_factory() as session:
        not_terminal = await _sweep_run_service.get_non_terminal_batches(session, run_id)

    if not_terminal:
        raise RuntimeError(
            f"{len(not_terminal)} batch(es) are not yet in a terminal state."
            " Run sweep.poll --wait first."
        )

    async with session_factory() as session:
        processable = await _sweep_run_service.get_processable_batches(session, run_id)

    if not processable:
        logger.info("No ended batches to process for run {}.", run_id)
        return

    batch_client = create_batch_client(tag.description)
    total_tagged = total_unsure = total_excluded = 0
    total_input = total_output = total_cache_read = total_cache_creation = 0
    all_failed_ids: list[str] = []

    for batch in processable:
        classified = await _classify_batch_results(batch_client, batch)
        await _apply_batch(batch, classified, tag.name, include_unsure, include_excluded)

        total_tagged += len(classified.tag_entries)
        total_unsure += len(classified.unsure_entries)
        total_excluded += len(classified.excluded_entries)
        all_failed_ids.extend(classified.failed_ids)
        total_input += classified.input_tokens
        total_output += classified.output_tokens
        total_cache_read += classified.cache_read_tokens
        total_cache_creation += classified.cache_creation_tokens

        cacheable = classified.input_tokens + classified.cache_read_tokens
        hit_pct = (classified.cache_read_tokens / cacheable * 100) if cacheable else 0.0
        batch_prefix = batch.batch_id[:20]
        logger.info(
            "Batch {} — tagged: {} | unsure: {} | excluded: {} | failed: {}",
            batch_prefix,
            len(classified.tag_entries),
            len(classified.unsure_entries),
            len(classified.excluded_entries),
            len(classified.failed_ids),
        )
        logger.info(
            "Batch {} — tokens in: {} out: {} cache_read: {} cache_write: {} (hit {:.0f}%)",
            batch_prefix,
            classified.input_tokens,
            classified.output_tokens,
            classified.cache_read_tokens,
            classified.cache_creation_tokens,
            hit_pct,
        )

    total_cacheable = total_input + total_cache_read
    total_hit_pct = (total_cache_read / total_cacheable * 100) if total_cacheable else 0.0
    logger.info(
        "Total — tagged: {} | unsure: {} | excluded: {} | failed: {}",
        total_tagged,
        total_unsure,
        total_excluded,
        len(all_failed_ids),
    )
    logger.info(
        "Total — tokens in: {} out: {} cache_read: {} cache_write: {} (hit {:.0f}%)",
        total_input,
        total_output,
        total_cache_read,
        total_cache_creation,
        total_hit_pct,
    )

    await _maybe_complete_run(run_id, tag)

    if all_failed_ids:
        logger.warning(
            "{} oracle ID(s) failed. Re-enqueue with:\n"
            "  uv run invoke sweep.kickoff --tag {} --reenqueue-failed",
            len(all_failed_ids),
            tag.name,
        )


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    asyncio.run(_run(args.run_id, args.include_unsure, args.include_excluded))


if __name__ == "__main__":
    main()
