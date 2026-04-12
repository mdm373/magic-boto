"""Sweep status response schemas."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel

from .audit_schema import AuditStatus

SweepStatusValue: TypeAlias = Literal["pending", "open", "auditing", "complete", "failed"]


class SweepEnqueueResult(BaseModel):
    sweep_id: str


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
    triggered_at: str
    completed_at: str | None
    batch_counts: BatchCounts
    audit: AuditStatus | None
