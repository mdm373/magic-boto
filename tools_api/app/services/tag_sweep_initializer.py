"""Submit Anthropic batch requests for tag sweep kickoff.

Celery pipeline enqueue is done by ``app.cmd.tag.sweep.enqueue`` (or workers), not here.
Pass one :class:`~sqlalchemy.ext.asyncio.AsyncSession` into :meth:`TagSweepInitializer.kickoff`
for the whole flow (DB may stay open across blocking Anthropic calls).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardModel
from app.repository import BatchChunkRecord, CardRepo, TagRepo, TagSweepRepo
from settings import get_settings

from .batch_client import BatchApiClient, Request, create_batch_client
from .card_payload import cards_to_csv

_PROMPTS_DIR = Path("app/prompts/sweep")
_SYSTEM_PROMPT_TEMPLATE = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_OUTPUT_SCHEMA_PATH = Path("app/message_schema/sweep_verdict.json")


def format_sweep_system_prompt(tag_description: str) -> str:
    """Format the sweep system prompt for a tag's description."""
    return _SYSTEM_PROMPT_TEMPLATE.format(tag_description=tag_description)


@dataclass(frozen=True, slots=True)
class SweepKickoffResult:
    """Return from :meth:`TagSweepInitializer.kickoff` for the CLI to optionally enqueue Celery."""

    run_id: uuid.UUID | None
    """Open run id when one exists or was created; otherwise ``None``."""

    batch_submitted: bool
    """True when new batch work was submitted."""


class TagSweepInitializer:
    """Create or resume a sweep run and submit batch work using injected dependencies."""

    def __init__(
        self,
        *,
        card_repo: CardRepo,
        sweep_repo: TagSweepRepo,
        tag_repo: TagRepo,
        batch_api_client: BatchApiClient,
    ) -> None:
        self._card_repo = card_repo
        self._sweep_repo = sweep_repo
        self._tag_repo = tag_repo
        self._batch_api_client = batch_api_client

    async def kickoff(
        self,
        session: AsyncSession,
        tag_name: str,
        limit: int,
        reenqueue_failed: bool,
    ) -> SweepKickoffResult:
        """Ensure an open run exists and submit batch work (one shared ``session`` for the flow)."""
        settings = get_settings()
        tag = await self._tag_repo.require_tag_model(session, tag_name)
        system_prompt = format_sweep_system_prompt(tag.description)
        logger.info("Using model: {}", settings.tag_sweep_model)

        run = await self._sweep_repo.get_open_sweep(session, tag.id)
        if run is None:
            run = await self._sweep_repo.create_sweep(session, tag.id)
            logger.info("Created new sweep run.")
        else:
            logger.info("Resuming existing run {}.", run.id)
        run_id = run.id

        logger.info("Run ID: {}", run_id)

        if reenqueue_failed:
            failed_ids = list(
                await self._sweep_repo.get_failed_oracle_ids_for_sweep(session, run_id)
            )
            if not failed_ids:
                logger.warning("Re-enqueue flagged for run with no failed ids")
                return SweepKickoffResult(run_id, batch_submitted=False)

            logger.info("Re-enqueueing {} failed oracle ID(s).", len(failed_ids))
            await self._submit_chunks(session, run_id, failed_ids, system_prompt, "reenqueue")
            return SweepKickoffResult(run_id, batch_submitted=True)

        tag_model = await self._tag_repo.require_tag_model_by_id(
            session, tag.id, load_relationships=True
        )
        eligible = list(
            await self._sweep_repo.fetch_eligible_oracle_ids(
                session, tag_model, run_id, limit=limit
            )
        )
        if not eligible:
            logger.info("No eligible cards to sweep")
            return SweepKickoffResult(run_id, batch_submitted=False)

        logger.info("{} eligible card(s) to submit.", len(eligible))
        await self._submit_chunks(session, run_id, eligible, system_prompt, "kickoff")
        return SweepKickoffResult(run_id, batch_submitted=True)

    async def _submit_chunks(
        self,
        session: AsyncSession,
        run_id: uuid.UUID,
        oracle_ids: list[str],
        system_prompt: str,
        label: str,
    ) -> None:
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
        rows = await self._card_repo.fetch_by_oracle_ids(session, all_oracle_ids)
        cards_by_oracle_id: dict[str, CardModel] = {c.oracle_id: c for c in rows}

        requests = self._build_anthropic_requests(records, cards_by_oracle_id, system_prompt)
        anthropic_batch_id = self._batch_api_client.submit_requests(requests)

        await self._sweep_repo.record_batch_with_cards(session, run_id, anthropic_batch_id, records)

        logger.info(
            "{}: submitted batch {} ({} cards in {} chunk(s))",
            label,
            anthropic_batch_id,
            len(oracle_ids),
            len(records),
        )

    def _build_anthropic_requests(
        self,
        records: Sequence[BatchChunkRecord],
        cards_by_oracle_id: Mapping[str, CardModel],
        system_prompt: str,
    ) -> list[Request]:
        settings = get_settings()
        return [
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
                output_schema_path=_OUTPUT_SCHEMA_PATH,
            )
            for record in records
        ]


def create_tag_sweep_initializer() -> TagSweepInitializer:
    """Wiring for CLI, Celery, and tests."""
    return TagSweepInitializer(
        card_repo=CardRepo(),
        sweep_repo=TagSweepRepo(),
        tag_repo=TagRepo(),
        batch_api_client=create_batch_client(),
    )
