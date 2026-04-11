"""Submit pending ``batches`` rows to Anthropic (outbox: one row per batch).

Outbox row updates go through :meth:`~app.repository.BatchRepo.apply_outbox_anthropic_batch_id`.
No flush/commit here — the session owner commits (e.g. ``worker_session`` / ``session_scope``).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
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

    async def submit_to_anthropic(
        self, batches: Sequence[BatchModel]
    ) -> Sequence[BatchSubmitResult]:
        """
        Submit a batch to Anthropic from the outboxand return the Anthropic batch ID.
        """
        request_batches: list[list[Request]] = []
        for batch in batches:
            if batch.anthropic_batch_id is not None:
                raise ValueError(f"Batch {batch.id} already submitted.")

            if batch.status != BatchStatus.PENDING_SUBMIT:
                raise ValueError(f"Batch {batch.id} is not pending submit.")

            if not batch.payload:
                raise ValueError(f"Batch {batch.id} missing payload.")
            request_batches.append(self._batch_serialization.deserialize_requests(batch.payload))
        results: list[BatchSubmitResult] = []
        for requests in request_batches:
            anthropic_batch_id = self._batch_api_client.submit_requests(requests)
            results.append(BatchSubmitResult(batch.id, anthropic_batch_id))
        return results


def create_batch_submit_service() -> BatchSubmitService:
    """Default wiring for workers and CLIs."""
    return BatchSubmitService(
        batch_api_client=create_batch_client(),
        batch_serialization=create_batch_serialization_service(),
    )


__all__ = ["BatchSubmitService", "create_batch_submit_service"]
