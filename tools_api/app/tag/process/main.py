"""Batch sweep process — apply tags from completed Anthropic batch results."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.models.sweep_run_batch import SweepRunBatchModel
from app.services import create_sweep_run_service, create_tag_service
from app.services.tag_service import CardTagEntry
from app.tag.batch.client import BatchSweepClient, create_batch_client
from app.tag.batch.verdict import Verdict
from settings import Settings, get_settings

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


def _parse_result_line(text: str) -> tuple[Verdict, str] | None:
    """Parse '{verdict} {reason}' from a model response line.

    Returns (verdict, reason) or None if the response is unparseable.
    """
    stripped = text.strip()
    raw_verdict, sep, reason = stripped.partition(" ")
    if not sep:
        return None
    try:
        verdict = Verdict(raw_verdict.strip().lower())
    except ValueError:
        return None
    return verdict, reason.strip()


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


def _classify_batch_results(
    batch_client: BatchSweepClient, batch: SweepRunBatchModel
) -> _BatchClassification:
    """Stream batch results and sort each into tag / unsure / excluded / failed buckets."""
    tag_entries: list[CardTagEntry] = []
    unsure_entries: list[CardTagEntry] = []
    excluded_entries: list[CardTagEntry] = []
    failed_ids: list[str] = []
    input_tokens = output_tokens = cache_read_tokens = cache_creation_tokens = 0

    for result in batch_client.get_results(batch.batch_id):
        oracle_id: str = result.custom_id

        if result.result.type != "succeeded":
            logger.warning(
                "Request {} in batch {} failed with type '{}'.",
                oracle_id,
                batch.batch_id,
                result.result.type,
            )
            failed_ids.append(oracle_id)
            continue

        usage = result.result.message.usage
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0

        text_blocks: list[Any] = [b for b in result.result.message.content if b.type == "text"]
        raw = text_blocks[0].text if text_blocks else ""
        parsed = _parse_result_line(raw)

        if parsed is None:
            logger.warning(
                "Unparseable response for {} in batch {}: {!r}",
                oracle_id,
                batch.batch_id,
                raw,
            )
            failed_ids.append(oracle_id)
            continue

        verdict, reason = parsed
        entry = CardTagEntry(oracle_id=oracle_id, reason=reason)

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
    batch_id: str,
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
        await _sweep_run_service.mark_batch_processed(session, batch_id)
        await session.commit()


async def _maybe_complete_run(run_id: uuid.UUID) -> None:
    """Mark the run complete when all cards are queued and all batches are processed."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        fresh_run = await _sweep_run_service.get_run(session, run_id)
        all_processed = await _sweep_run_service.are_all_batches_processed(session, run_id)

        if fresh_run is not None and fresh_run.all_cards_queued and all_processed:
            await _sweep_run_service.complete_run(session, run_id)
            await session.commit()
            logger.info("Run {} marked complete.", run_id)
        else:
            remaining = await _sweep_run_service.get_non_terminal_batches(session, run_id)
            logger.info(
                "Run {} remains open ({} batch(es) not yet processed, all_cards_queued={}).",
                run_id,
                len(remaining),
                fresh_run.all_cards_queued if fresh_run else "?",
            )


def _write_failed_ids(
    failed_ids: list[str], run_id: uuid.UUID, tag_name: str, settings: Settings
) -> None:
    """Persist failed oracle IDs to disk and log a re-enqueue command."""
    debug_dir = Path(settings.debug_output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    failed_path = debug_dir / f"failed_ids_{run_id}.txt"
    failed_path.write_text("\n".join(failed_ids))
    logger.warning(
        "{} request(s) failed. Oracle IDs written to {}.\n"
        "Re-enqueue with:\n"
        "  uv run invoke sweep.kickoff --tag {} --oracle-ids-file {}",
        len(failed_ids),
        failed_path,
        tag_name,
        failed_path,
    )


async def _run(run_id_str: str, include_unsure: bool, include_excluded: bool) -> None:
    run_id = uuid.UUID(run_id_str)
    settings = get_settings()

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        run = await _sweep_run_service.get_run(session, run_id)
        if run is None:
            raise ValueError(f"Sweep run {run_id} not found.")
        tag = await _tag_service.require_tag_model_by_id(session, run.tag_id)

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
        classified = _classify_batch_results(batch_client, batch)
        await _apply_batch(batch.batch_id, classified, tag.name, include_unsure, include_excluded)

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

    await _maybe_complete_run(run_id)

    if all_failed_ids:
        _write_failed_ids(all_failed_ids, run_id, tag.name, settings)


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    asyncio.run(_run(args.run_id, args.include_unsure, args.include_excluded))


if __name__ == "__main__":
    main()
