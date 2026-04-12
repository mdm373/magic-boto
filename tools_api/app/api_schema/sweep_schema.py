"""Sweep status response schemas."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel

AuditStatusValue: TypeAlias = Literal["pending", "in_progress", "complete", "failed"]
SweepStatusValue: TypeAlias = Literal["pending", "open", "auditing", "complete", "failed"]


class SweepEnqueueResult(BaseModel):
    sweep_id: str


class BatchCounts(BaseModel):
    total: int
    pending: int
    submitted: int
    complete: int
    failed: int


class AuditStatus(BaseModel):
    audit_id: str
    status: AuditStatusValue
    report: str | None


class SweepStatusResponse(BaseModel):
    sweep_id: str
    tag_name: str
    status: SweepStatusValue
    triggered_at: str
    completed_at: str | None
    batch_counts: BatchCounts
    audit: AuditStatus | None
