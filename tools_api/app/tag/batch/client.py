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
from app.tag.card_payload import card_to_dict
from settings import get_settings

_PROMPTS_DIR = Path(__file__).parent
_SYSTEM_PROMPT_TEMPLATE = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()


@dataclass(frozen=True, slots=True)
class BatchStatus:
    processing_status: str
    ended_at: datetime | None


def _build_system_prompt(tag_description: str) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(tag_description=tag_description)


def _card_to_user_message(card: MagicBotoCardModel) -> str:
    """Serialise card to compact JSON, omitting oracle_id (identity comes from custom_id)."""
    payload = {k: v for k, v in card_to_dict(card).items() if k != "oracle_id"}
    return json.dumps(payload, separators=(",", ":"))


class BatchSweepClient:
    """Thin wrapper around the Anthropic Batch API for single-card sweep requests."""

    def __init__(
        self,
        batches: Batches,
        model: str,
        tag_description: str,
        max_requests_per_batch: int,
        max_tokens: int,
    ) -> None:
        self._batches = batches
        self._model = model
        self._system_prompt = _build_system_prompt(tag_description)
        self.max_requests_per_batch = max_requests_per_batch
        self._max_tokens = max_tokens

    def submit_batch(self, cards: Sequence[MagicBotoCardModel]) -> str:
        """Submit one batch request per card. Returns the Anthropic batch ID."""
        requests = [
            {
                "custom_id": str(card.oracle_id),
                "params": {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "system": [
                        {
                            "type": "text",
                            "text": self._system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [{"role": "user", "content": _card_to_user_message(card)}],
                },
            }
            for card in cards
        ]
        batch = self._batches.create(requests=requests)  # type: ignore[arg-type]
        return batch.id

    def get_batch_status(self, batch_id: str) -> BatchStatus:
        """Return status for the given batch.

        processing_status mirrors the Anthropic API:
          'in_progress' | 'canceling' | 'ended'
        ended_at is set when the batch reaches a terminal state.
        """
        batch = self._batches.retrieve(batch_id)
        status = batch.processing_status
        ended_at: datetime | None = None
        if status == "ended":
            raw = getattr(batch, "ended_at", None)
            ended_at = raw if isinstance(raw, datetime) else datetime.now(UTC)
        return BatchStatus(processing_status=status, ended_at=ended_at)

    def get_results(self, batch_id: str) -> Sequence[BetaMessageBatchIndividualResponse]:
        """Return all MessageBatchResult objects for the batch."""
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
        settings.batch_api_max_requests,
        settings.tag_sweep_max_tokens,
    )
