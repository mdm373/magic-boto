"""Anthropic Messages Batch API client."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import anthropic
from anthropic.resources.beta.messages.batches import Batches
from anthropic.types.beta.message_create_params import (
    MessageCreateParamsNonStreaming as BatchParams,
)
from anthropic.types.beta.messages import BetaMessageBatchIndividualResponse
from anthropic.types.beta.messages.batch_create_params import Request as BatchRequest
from loguru import logger

from settings import get_settings

BATCH_DIR = Path(__file__).parent


def _parse_ended_at(anthropic_batch_id: str, batch: object) -> datetime | None:
    raw = getattr(batch, "ended_at", None)
    if isinstance(raw, datetime):
        return raw
    logger.warning(
        "Batch {} ended but ended_at is missing or unexpected type ({}).",
        anthropic_batch_id,
        type(raw),
    )
    return None


@dataclass(frozen=True, slots=True)
class Request:
    """A single request to submit inside an Anthropic batch."""

    custom_id: str
    messages: Sequence[str]
    model: str
    max_tokens: int
    system_prompt: str = ""
    output_schema_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ApiBatchStatus:
    """Status snapshot returned from the Anthropic batch API."""

    processing_status: str
    ended_at: datetime | None


class BatchApiClient:
    """Thin wrapper around the Anthropic Batch API.

    Call :meth:`submit_requests` to submit a batch, and
    :meth:`get_batch_status` / :meth:`get_results` to poll and retrieve.
    """

    def __init__(self, batches: Batches) -> None:
        self._batches = batches

    def submit_requests(self, requests: Sequence[Request]) -> str:
        """Build and submit one Anthropic batch request per :class:`Request`.

        Returns the Anthropic batch ID.
        """
        payload: list[BatchRequest] = []
        for req in requests:
            output_schema: dict[str, object] | None = (
                json.loads(req.output_schema_path.read_text())
                if req.output_schema_path is not None
                else None
            )
            params: BatchParams = {
                "model": req.model,
                "max_tokens": req.max_tokens,
                "messages": [{"role": "user", "content": msg} for msg in req.messages],
            }
            if req.system_prompt:
                params["system"] = req.system_prompt
            if output_schema is not None:
                params["output_config"] = {
                    "format": {"type": "json_schema", "schema": output_schema}
                }
            payload.append({"custom_id": req.custom_id, "params": params})

        batch = self._batches.create(requests=payload)
        return batch.id

    def get_batch_status(self, anthropic_batch_id: str) -> ApiBatchStatus:
        """Return status for the given Anthropic batch ID."""
        batch = self._batches.retrieve(anthropic_batch_id)
        status = batch.processing_status
        ended_at = _parse_ended_at(anthropic_batch_id, batch) if status == "ended" else None
        return ApiBatchStatus(processing_status=status, ended_at=ended_at)

    def get_results(self, anthropic_batch_id: str) -> Sequence[BetaMessageBatchIndividualResponse]:
        """Return all result objects for the batch (one per request)."""
        return list(self._batches.results(anthropic_batch_id))


def create_batch_client() -> BatchApiClient:
    """Build a BatchApiClient — suitable for any batch operation."""
    settings = get_settings()
    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set — required for batch API calls.")
    return BatchApiClient(anthropic.Anthropic(api_key=api_key).beta.messages.batches)
