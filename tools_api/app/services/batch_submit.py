"""Submit pending ``batches`` rows to Anthropic (outbox: one row per batch).

Outbox row updates go through :meth:`~app.repository.BatchRepo.apply_outbox_anthropic_batch_id`.
No flush/commit here — the session owner commits (e.g. ``worker_session`` / ``session_scope``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models import BatchModel, BatchStatus

from .batch_client import BatchApiClient, Request, create_batch_client
from .batch_serialization_service import (
    BatchSerializationService,
    create_batch_serialization_service,
)


@dataclass(frozen=True, slots=True)
class BatchSubmitResult:
    batch_uuid: uuid.UUID
    anthropic_batch_id: str


class BatchSubmitService:
    """Outbox submit: load ``batches`` row, deserialize ``payload``, call Anthropic."""

    def __init__(
        self,
        *,
        batch_api_client: BatchApiClient,
        batch_serialization: BatchSerializationService,
    ) -> None:
        self._batch_api_client = batch_api_client
        self._batch_serialization = batch_serialization

    async def submit_to_anthropic(self, batch: BatchModel) -> BatchSubmitResult:
        """Submit one outbox batch to Anthropic and return its Anthropic batch ID.

        One batch per call so the caller can commit each Anthropic ID before submitting the
        next — a later failure must not orphan batches Anthropic already accepted.
        """
        if batch.anthropic_batch_id is not None:
            raise ValueError(f"Batch {batch.id} already submitted.")

        if batch.status != BatchStatus.PENDING_SUBMIT:
            raise ValueError(f"Batch {batch.id} is not pending submit.")

        if not batch.payload:
            raise ValueError(f"Batch {batch.id} missing payload.")
        requests: list[Request] = self._batch_serialization.deserialize_requests(batch.payload)
        anthropic_batch_id = self._batch_api_client.submit_requests(requests)
        return BatchSubmitResult(batch.id, anthropic_batch_id)


def create_batch_submit_service() -> BatchSubmitService:
    """Default wiring for workers and CLIs."""
    return BatchSubmitService(
        batch_api_client=create_batch_client(),
        batch_serialization=create_batch_serialization_service(),
    )


__all__ = ["BatchSubmitService", "create_batch_submit_service"]
