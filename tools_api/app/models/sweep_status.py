"""Status enums for sweep runs and their Anthropic batch requests."""

from __future__ import annotations

from enum import StrEnum


class SweepRunStatus(StrEnum):
    OPEN = "open"
    COMPLETE = "complete"
    FAILED = "failed"


class BatchStatus(StrEnum):
    PENDING_SUBMIT = "pending_submit"  # outbox row; payload set, not yet sent to Anthropic
    SUBMITTED = "submitted"  # accepted by Anthropic Batch API; poll drives later states
    IN_PROGRESS = "in_progress"
    CANCELING = "canceling"
    ENDED = "ended"  # Anthropic finished; individual results available
    PROCESSED = "processed"  # results have been consumed and applied
    ERRORED = "errored"
    EXPIRED = "expired"
    CANCELED = "canceled"


# Lifecycle order for comparisons (``<= ceiling`` deletes this status and all earlier rows).
BATCH_STATUS_PIPELINE_ORDER: tuple[BatchStatus, ...] = (
    BatchStatus.PENDING_SUBMIT,
    BatchStatus.SUBMITTED,
    BatchStatus.IN_PROGRESS,
    BatchStatus.CANCELING,
    BatchStatus.ENDED,
    BatchStatus.PROCESSED,
    BatchStatus.ERRORED,
    BatchStatus.EXPIRED,
    BatchStatus.CANCELED,
)


def batch_statuses_at_or_before(ceiling: BatchStatus) -> frozenset[BatchStatus]:
    """Statuses from the pipeline at or before ``ceiling`` (inclusive)."""
    order = BATCH_STATUS_PIPELINE_ORDER
    try:
        idx = order.index(ceiling)
    except ValueError as e:
        raise ValueError(f"Unknown batch status for ceiling: {ceiling!r}") from e
    return frozenset(order[: idx + 1])


def parse_batch_status(raw: str) -> BatchStatus:
    """Parse CLI/user input by normalizing to a :class:`BatchStatus` member name (``.upper()``)."""
    key = raw.strip().replace("-", "_").upper()
    if not key:
        raise ValueError("Batch status is required.")
    try:
        return BatchStatus[key]
    except KeyError as e:
        allowed = ", ".join(s.name for s in BATCH_STATUS_PIPELINE_ORDER)
        raise ValueError(f"Invalid batch status {raw!r}; use one of: {allowed}") from e


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
