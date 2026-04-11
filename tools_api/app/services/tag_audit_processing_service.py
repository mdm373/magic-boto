"""Fetch audit batch results, persist report, save to debug file.

Used by ``app.cmd.tag.audit.process`` and the Celery audit pipeline.
Callers pass one :class:`~sqlalchemy.ext.asyncio.AsyncSession` for the whole run
(DB may stay open across blocking Anthropic ``get_results``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BatchStatus, TagModel
from app.repository import BatchRepo, TagAuditRepo
from settings import get_settings

from .batch_client import BatchApiClient, create_batch_client

_SUGGESTION_MARKER = "## Suggested Description"


def _extract_suggestion(report: str) -> str | None:
    """Extract the '## Suggested Description' section from an audit report."""
    idx = report.find(_SUGGESTION_MARKER)
    if idx == -1:
        return None
    return report[idx + len(_SUGGESTION_MARKER) :].strip()


class TagAuditProcessingService:
    """Load audit batch results using injected repos and Anthropic batch API client."""

    def __init__(
        self,
        *,
        audit_repo: TagAuditRepo,
        batch_repo: BatchRepo,
        batch_api_client: BatchApiClient,
    ) -> None:
        self._audit_repo = audit_repo
        self._batch_repo = batch_repo
        self._batch_api_client = batch_api_client

    async def run(self, session: AsyncSession, audit_id_str: str) -> None:
        """Load ENDED audit batch results, persist report and suggestion, write markdown file."""
        audit_id = uuid.UUID(audit_id_str)
        audit = await self._audit_repo.get_audit(session, audit_id)
        if audit is None:
            raise ValueError(f"Audit {audit_id} not found.")
        if audit.batch is None:
            raise ValueError(f"Audit {audit_id} has no batch — run kickoff first.")
        if audit.batch.status != BatchStatus.ENDED:
            raise ValueError(
                f"Batch is not in ENDED state (current: {audit.batch.status}). "
                "Wait for the Celery audit pipeline or run "
                "`uv run python -m app.cmd.tag.audit.enqueue --audit-id <id>` "
                "or `uv run invoke audit.enqueue --audit-id=<id>`."
            )
        if audit.report is not None:
            logger.warning("Audit {} already has a report — re-processing.", audit_id)

        anthropic_batch_id = audit.batch.anthropic_batch_id
        if anthropic_batch_id is None:
            raise ValueError(
                "Audit batch is missing anthropic_batch_id (unexpected for this status)."
            )

        results = self._batch_api_client.get_results(anthropic_batch_id)

        report: str | None = None
        for result in results:
            if result.result.type == "succeeded":
                text_blocks = [b for b in result.result.message.content if b.type == "text"]
                if text_blocks:
                    report = text_blocks[0].text.strip()
            else:
                raise ValueError(
                    f"Audit batch request failed with type '{result.result.type}'. Cannot process."
                )

        if report is None:
            raise ValueError("No text content in audit batch response.")

        suggestion = _extract_suggestion(report)
        if suggestion is None:
            logger.warning("No '## Suggested Description' section found in audit report.")

        audit = await self._audit_repo.get_audit(session, audit_id)
        if audit is None or audit.batch is None:
            raise ValueError(f"Audit {audit_id} disappeared during processing.")
        await self._audit_repo.set_report_and_suggestion(
            session,
            audit,
            report=report,
            suggestion=suggestion,
        )
        await self._batch_repo.mark_batch_processed(session, audit.batch)
        tag_row = await session.scalar(select(TagModel).where(TagModel.id == audit.tag_id))
        if tag_row is None:
            raise ValueError(f"Tag {audit.tag_id} not found for audit {audit_id}.")
        tag_name = tag_row.name

        self._write_debug_report_file(report, tag_name)

    def _write_debug_report_file(
        self,
        report: str,
        tag_name: str,
    ) -> None:
        """Write markdown audit file and optionally open it (Windows)."""
        s = get_settings()
        debug_dir = Path(s.debug_output_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_path = debug_dir / f"{timestamp}_{tag_name}_audit.md"
        output_path.write_text(report, encoding="utf-8")
        logger.info("Audit report saved to {}.", output_path)


def create_tag_audit_processing_service() -> TagAuditProcessingService:
    """Wiring for CLI, Celery, and tests."""
    return TagAuditProcessingService(
        audit_repo=TagAuditRepo(),
        batch_repo=BatchRepo(),
        batch_api_client=create_batch_client(),
    )
