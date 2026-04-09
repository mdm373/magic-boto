"""Apply tags from completed Anthropic batch results for a sweep run.

Used by ``app.cmd.tag.sweep.process`` and the Celery sweep pipeline.
Caller supplies one ``AsyncSession`` and commits (e.g. ``worker_session``).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from anthropic.types.beta import BetaTextBlock
from loguru import logger
from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BatchModel, TagModel, TagSweepBatchModel
from app.repository import BatchRepo, CardTagEntry, TagRepo, TagSweepRepo

from .batch_client import BatchApiClient, create_batch_client
from .batch_verdict import Verdict
from .tag_service import TagService


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


class TagSweepProcessor:
    """Apply sweep verdicts using injected repos, tag service, and Anthropic batch API client."""

    def __init__(
        self,
        *,
        sweep_repo: TagSweepRepo,
        batch_repo: BatchRepo,
        tag_repo: TagRepo,
        tag_service: TagService,
        batch_api_client: BatchApiClient,
    ) -> None:
        self._sweep_repo = sweep_repo
        self._batch_repo = batch_repo
        self._tag_repo = tag_repo
        self._tag_service = tag_service
        self._batch_api_client = batch_api_client

    async def run(
        self,
        session: AsyncSession,
        tag_name: str,
        include_unsure: bool,
        include_excluded: bool,
    ) -> None:
        """Apply sweep verdicts for the open run. Raises if batches are not yet terminal."""
        tag = await self._tag_repo.require_tag_model(session, tag_name, load_relationships=True)
        run = await self._sweep_repo.get_open_sweep(session, tag.id)
        if run is None:
            raise ValueError(f"No open sweep found for tag '{tag_name}'.")

        sweep_id = run.id
        await self._ensure_side_tags(session, tag.name, include_unsure, include_excluded)
        not_terminal = await self._sweep_repo.get_non_terminal_batches(session, sweep_id)
        if not_terminal:
            raise RuntimeError(f"{len(not_terminal)} batch(es) are not yet in a terminal state.")

        processable = await self._sweep_repo.get_processable_batches(session, sweep_id)
        if not processable:
            logger.info("No ended batches to process for run {}.", sweep_id)
            return

        total_tagged = total_unsure = total_excluded = 0
        total_input = total_output = total_cache_read = total_cache_creation = 0
        all_failed_ids: list[str] = []
        name = tag.name
        for batch in processable:
            cls = await self._classify_batch_results(session, batch)
            await self._apply_batch(session, batch, cls, name, include_unsure, include_excluded)
            total_tagged += len(cls.tag_entries)
            total_unsure += len(cls.unsure_entries)
            total_excluded += len(cls.excluded_entries)
            all_failed_ids.extend(cls.failed_ids)
            total_input += cls.input_tokens
            total_output += cls.output_tokens
            total_cache_read += cls.cache_read_tokens
            total_cache_creation += cls.cache_creation_tokens
            cacheable = cls.input_tokens + cls.cache_read_tokens
            hit_pct = (cls.cache_read_tokens / cacheable * 100) if cacheable else 0.0
            batch_prefix = batch.batch.anthropic_batch_id[:20]
            logger.info(
                "Batch {} — tagged: {} | unsure: {} | excluded: {} | failed: {}",
                batch_prefix,
                len(cls.tag_entries),
                len(cls.unsure_entries),
                len(cls.excluded_entries),
                len(cls.failed_ids),
            )
            logger.info(
                "Batch {} — tokens in: {} out: {} cache_read: {} cache_write: {} (hit {:.0f}%)",
                batch_prefix,
                cls.input_tokens,
                cls.output_tokens,
                cls.cache_read_tokens,
                cls.cache_creation_tokens,
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

        await self._maybe_complete_sweep(session, sweep_id, tag)
        if all_failed_ids:
            logger.warning(
                "{} oracle ID(s) failed. Re-enqueue with:\n"
                "  uv run python -m app.cmd.tag.sweep.enqueue {} --reenqueue-failed\n"
                "  or uv run invoke sweep.enqueue --tag {} --reenqueue-failed",
                len(all_failed_ids),
                tag.name,
                tag.name,
            )

    async def _ensure_side_tags(
        self,
        session: AsyncSession,
        tag_name: str,
        include_unsure: bool,
        include_excluded: bool,
    ) -> None:
        """Create _unsure / _excluded side-tags if they are needed and don't yet exist."""
        unsure_tag = await self._tag_repo.get_tag(session, f"{tag_name}_unsure")
        if include_unsure and unsure_tag is None:
            await self._tag_repo.create_tag(
                session,
                f"{tag_name}_unsure",
                f"Cards flagged for manual review during the '{tag_name}' tag sweep.",
            )
            logger.info("Created tag '{}_unsure'.", tag_name)
        excluded_tag = await self._tag_repo.get_tag(session, f"{tag_name}_excluded")
        if include_excluded and excluded_tag is None:
            await self._tag_repo.create_tag(
                session,
                f"{tag_name}_excluded",
                f"Cards that do not qualify for '{tag_name}', as determined by the tag sweep.",
            )
            logger.info("Created tag '{}_excluded'.", tag_name)

    async def _classify_batch_results(
        self,
        session: AsyncSession,
        sweep_batch: TagSweepBatchModel,
    ) -> _BatchClassification:
        """Stream results; sort each chunk into tag / unsure / excluded / failed buckets."""
        tag_entries: list[CardTagEntry] = []
        unsure_entries: list[CardTagEntry] = []
        excluded_entries: list[CardTagEntry] = []
        failed_ids: list[str] = []
        input_tokens = output_tokens = cache_read_tokens = cache_creation_tokens = 0
        anthropic_batch_id = sweep_batch.batch.anthropic_batch_id
        for result in self._batch_api_client.get_results(anthropic_batch_id):
            chunk_custom_id: str = result.custom_id
            if result.result.type != "succeeded":
                logger.warning(
                    "Chunk {} in batch {} failed with type '{}'.",
                    chunk_custom_id,
                    anthropic_batch_id,
                    result.result.type,
                )
                chunk_cards = await self._sweep_repo.get_batch_cards(
                    session, sweep_batch.id, chunk_custom_id
                )
                failed_ids.extend(c.oracle_id for c in chunk_cards)
                continue

            usage = result.result.message.usage
            input_tokens += usage.input_tokens
            output_tokens += usage.output_tokens
            cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
            text_blocks: list[BetaTextBlock] = [
                b for b in result.result.message.content if b.type == "text"
            ]
            raw = text_blocks[0].text if text_blocks else ""

            chunk_cards = await self._sweep_repo.get_batch_cards(
                session, sweep_batch.id, chunk_custom_id
            )
            verdicts = _parse_verdicts(raw, expected=len(chunk_cards))
            missing = len(chunk_cards) - len(verdicts)
            if missing > 0:
                logger.warning(
                    "Chunk {} in batch {}: {} of {} verdicts missing — failing those cards.",
                    chunk_custom_id,
                    anthropic_batch_id,
                    missing,
                    len(chunk_cards),
                )
            for i, card_row in enumerate(chunk_cards):
                verdict = verdicts.get(i)
                if verdict is None:
                    failed_ids.append(card_row.oracle_id)
                    continue
                entry = CardTagEntry(oracle_id=card_row.oracle_id)
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
        self,
        session: AsyncSession,
        sweep_batch: TagSweepBatchModel,
        classified: _BatchClassification,
        tag_name: str,
        include_unsure: bool,
        include_excluded: bool,
    ) -> None:
        """Persist tag assignments for one batch and mark it processed."""
        if classified.tag_entries:
            await self._tag_service.add_card_tags(session, tag_name, classified.tag_entries)
        if include_unsure and classified.unsure_entries:
            await self._tag_service.add_card_tags(
                session, f"{tag_name}_unsure", classified.unsure_entries
            )
        if include_excluded and classified.excluded_entries:
            await self._tag_service.add_card_tags(
                session, f"{tag_name}_excluded", classified.excluded_entries
            )
        if classified.failed_ids:
            await self._sweep_repo.mark_batch_cards_failed(
                session, sweep_batch.id, classified.failed_ids
            )
        batch = await session.scalar(
            _select(BatchModel).where(BatchModel.id == sweep_batch.batch_id)
        )
        if batch is not None:
            self._batch_repo.mark_batch_processed(batch)

    async def _maybe_complete_sweep(
        self, session: AsyncSession, sweep_id: uuid.UUID, tag: TagModel
    ) -> None:
        """Mark the run complete when all batches are processed and no eligible cards remain."""
        complete = await self._sweep_repo.is_sweep_complete(session, sweep_id, tag)
        if complete:
            await self._sweep_repo.complete_sweep(session, sweep_id)
            logger.info("Run {} marked complete.", sweep_id)
            return

        remaining = await self._sweep_repo.get_non_terminal_batches(session, sweep_id)
        eligible = await self._sweep_repo.fetch_eligible_oracle_ids(session, tag, sweep_id)
        logger.info(
            "Run {} remains open ({} batch(es) not yet processed, {} eligible card(s) remaining).",
            sweep_id,
            len(remaining),
            len(eligible),
        )


def create_tag_sweep_processor() -> TagSweepProcessor:
    """Wiring for CLI, Celery, and tests."""
    return TagSweepProcessor(
        sweep_repo=TagSweepRepo(),
        batch_repo=BatchRepo(),
        tag_repo=TagRepo(),
        tag_service=TagService(),
        batch_api_client=create_batch_client(),
    )


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
