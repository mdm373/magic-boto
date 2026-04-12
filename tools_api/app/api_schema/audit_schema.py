"""Audit apply and query response schemas."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel

AuditStatusValue: TypeAlias = Literal["pending", "in_progress", "complete", "failed"]


class AuditStatus(BaseModel):
    audit_id: str
    status: AuditStatusValue
    report: str | None


class ApplyAuditResult(BaseModel):
    tag_name: str
    new_description: str
    cards_cleared: int
    sweep_reset: bool


class AuditResponse(BaseModel):
    audit_id: str
    tag_name: str
    status: AuditStatusValue
    report: str | None
    suggestion: str | None
    triggered_at: str
