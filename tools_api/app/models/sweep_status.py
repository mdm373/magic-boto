"""Status enums for sweep runs and their Anthropic batch requests."""

from __future__ import annotations

from enum import StrEnum


class SweepRunStatus(StrEnum):
    OPEN = "open"
    COMPLETE = "complete"
    FAILED = "failed"


class BatchStatus(StrEnum):
    SUBMITTED = "submitted"  # recorded locally, not yet confirmed by Anthropic
    IN_PROGRESS = "in_progress"
    CANCELING = "canceling"
    ENDED = "ended"  # Anthropic finished; individual results available
    PROCESSED = "processed"  # results have been consumed and applied
    ERRORED = "errored"
    EXPIRED = "expired"
    CANCELED = "canceled"


# Batches that will not change state.
TERMINAL_BATCH_STATUSES: frozenset[BatchStatus] = frozenset(
    {
        BatchStatus.ENDED,
        BatchStatus.PROCESSED,
        BatchStatus.ERRORED,
        BatchStatus.EXPIRED,
        BatchStatus.CANCELED,
    }
)

# Batches whose results can be downloaded and applied.
PROCESSABLE_BATCH_STATUSES: frozenset[BatchStatus] = frozenset(
    {
        BatchStatus.ENDED,
    }
)

# Batches that failed without producing results; their cards need re-enqueueing.
FAILED_BATCH_STATUSES: frozenset[BatchStatus] = frozenset(
    {
        BatchStatus.ERRORED,
        BatchStatus.EXPIRED,
        BatchStatus.CANCELED,
    }
)
