"""Sweep status response schemas."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel

from .audit_schema import AuditStatus

SweepStatusValue: TypeAlias = Literal["pending", "open", "auditing", "complete", "failed"]


class SweepEnqueueResult(BaseModel):
    sweep_id: str


class CleanTagSweepResetResult(BaseModel):
    """Counters from ``clean_reset_tag_sweep``."""

    tag_name: str
    deleted_sweep_id: str | None
    cards_cleared: int
    batches_deleted: int


class BatchCounts(BaseModel):
    total: int
    pending: int
    submitted: int
    complete: int
    failed: int


class SweepStatusResponse(BaseModel):
    sweep_id: str
    tag_name: str
    status: SweepStatusValue
    requested_limit: int | None = None
    triggered_at: str
    completed_at: str | None
    batch_counts: BatchCounts
    audit: AuditStatus | None


class SweepListRow(SweepStatusResponse):
    """Same fields as :class:`SweepStatusResponse` for list endpoints."""


class SweepListResponse(BaseModel):
    rows: list[SweepListRow]


class GlobalSweepCatchupTagResult(BaseModel):
    tag_name: str
    sweep_id: str
    enqueued: bool
    error: str | None = None


class GlobalSweepCatchupResult(BaseModel):
    """Aggregate result of ``enqueue_global_sweep_catchup``."""

    tags_considered: int
    enqueued_count: int
    skipped_count: int
    tags: list[GlobalSweepCatchupTagResult]
