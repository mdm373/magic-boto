"""Anthropic Messages Batch API client for the tag sweep pipeline."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import anthropic
from anthropic.resources.beta.messages.batches import Batches
from anthropic.types.beta.messages import BetaMessageBatchIndividualResponse

from app.models.magic_boto_card import MagicBotoCardModel
from app.tag.card_payload import cards_to_csv
from settings import get_settings

_PROMPTS_DIR = Path(__file__).parent
_SYSTEM_PROMPT_TEMPLATE = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_OUTPUT_SCHEMA: dict = json.loads((_PROMPTS_DIR / "output_schema.json").read_text())


@dataclass(frozen=True, slots=True)
class BatchChunk:
    """A chunk of cards to submit as one request within an Anthropic batch."""

    custom_id: str
    cards: Sequence[MagicBotoCardModel]


@dataclass(frozen=True, slots=True)
class BatchChunkRecord:
    """The oracle_id manifest for a submitted chunk — used to record in the DB."""

    custom_id: str
    oracle_ids: Sequence[str]


@dataclass(frozen=True, slots=True)
class BatchStatus:
    processing_status: str
    ended_at: datetime | None


def _build_system_prompt(tag_description: str) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(tag_description=tag_description)


class BatchSweepClient:
    """Thin wrapper around the Anthropic Batch API for CSV-chunk sweep requests."""

    def __init__(
        self,
        batches: Batches,
        model: str,
        tag_description: str,
        max_tokens: int,
    ) -> None:
        self._batches = batches
        self._model = model
        self._system_prompt = _build_system_prompt(tag_description)
        self._max_tokens = max_tokens

    def submit_batch(self, chunks: Sequence[BatchChunk]) -> str:
        """Submit one request per chunk inside a single Anthropic batch.

        Returns the Anthropic batch ID.
        """
        requests = [
            {
                "custom_id": chunk.custom_id,
                "params": {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "system": self._system_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": cards_to_csv(chunk.cards),
                        },
                    ],
                    "output_config": {
                        "format": {
                            "type": "json_schema",
                            "schema": _OUTPUT_SCHEMA,
                        }
                    },
                },
            }
            for chunk in chunks
        ]
        batch = self._batches.create(requests=requests)  # type: ignore[arg-type]
        return batch.id

    def get_batch_status(self, batch_id: str) -> BatchStatus:
        """Return status for the given batch."""
        batch = self._batches.retrieve(batch_id)
        status = batch.processing_status
        ended_at: datetime | None = None
        if status == "ended":
            raw = getattr(batch, "ended_at", None)
            ended_at = raw if isinstance(raw, datetime) else datetime.now(UTC)
        return BatchStatus(processing_status=status, ended_at=ended_at)

    def get_results(self, batch_id: str) -> Sequence[BetaMessageBatchIndividualResponse]:
        """Return all result objects for the batch (one per chunk request)."""
        return list(self._batches.results(batch_id))


def create_batch_client(tag_description: str) -> BatchSweepClient:
    """Build a BatchSweepClient from settings."""
    settings = get_settings()
    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set — required for the batch sweep client.")
    return BatchSweepClient(
        anthropic.Anthropic(api_key=api_key).beta.messages.batches,
        settings.tag_sweep_model,
        tag_description,
        settings.tag_sweep_max_tokens,
    )
