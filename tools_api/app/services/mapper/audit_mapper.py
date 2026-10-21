"""Audit mapper: convert ORM audit models to API response schemas."""

from app.api_schema import AuditResponse, AuditStatus, AuditStatusValue
from app.models import FAILED_BATCH_STATUSES, TagAuditModel


class AuditMapper:
    """Map ORM audit model to API response schemas."""

    def status(self, audit: TagAuditModel) -> AuditStatusValue:
        """Derive audit progress from its batch and report."""
        if audit.batch_id is None:
            return "pending"
        if audit.report is not None:
            return "complete"
        if audit.batch is not None and audit.batch.status in FAILED_BATCH_STATUSES:
            return "failed"
        return "in_progress"

    def to_status(self, audit: TagAuditModel) -> AuditStatus:
        return AuditStatus(
            audit_id=str(audit.id),
            status=self.status(audit),
            report=audit.report,
        )

    def to_response(self, audit: TagAuditModel, tag_name: str) -> AuditResponse:
        return AuditResponse(
            audit_id=str(audit.id),
            tag_name=tag_name,
            status=self.status(audit),
            report=audit.report,
            suggestion=audit.suggestion,
            triggered_at=audit.triggered_at.isoformat(),
        )
