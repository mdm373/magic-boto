"""MCP sweep tool registrations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema.sweep_schema import (
    AuditStatus,
    AuditStatusValue,
    BatchCounts,
    SweepEnqueueResult,
    SweepStatusResponse,
    SweepStatusValue,
)
from app.errors import InvalidRequestError, NotFoundError
from app.models import FAILED_BATCH_STATUSES, BatchStatus, SweepRunStatus, TagModel, TagSweepModel
from app.repository import TagAuditRepo, TagRepo, TagSweepRepo
from app.services.tag_sweep_initializer import SweepKickoffRequest, create_tag_sweep_initializer
from app.worker import enqueue_materialize_sweep_batches

from .error_middleware import AppMcp

_UI_DIST = Path(__file__).parent / "ui_dist"
_UI_MIME_TYPE = "text/html;profile=mcp-app"
_FALLBACK_HTML = (
    "<!doctype html><html><body style='font-family:sans-serif;padding:1rem'>"
    "<p>UI not built. Run <code>npm run build</code> inside "
    "<code>tools-ui/</code>.</p></body></html>"
)
_SWEEP_RESOURCE_URI = "ui://magic-boto/sweep"

_sweep_repo = TagSweepRepo()
_audit_repo = TagAuditRepo()
_tag_repo = TagRepo()
_sweep_initializer = create_tag_sweep_initializer()


@dataclass(frozen=True, slots=True)
class ResolvedSweepForStatus:
    """ORM sweep row plus tag name for API responses (from sweep_id or tag_name lookup)."""

    sweep: TagSweepModel
    tag_name: str


async def _resolve_sweep_for_status_query(
    session: AsyncSession,
    *,
    sweep_id_str: str,
    tag_name_str: str,
) -> ResolvedSweepForStatus:
    """Load sweep by UUID or by tag name. Precondition: exactly one of the strings is non-empty."""
    if sweep_id_str:
        try:
            sid = uuid.UUID(sweep_id_str)
        except ValueError as e:
            raise InvalidRequestError(f"Invalid sweep_id {sweep_id_str!r}.") from e
        sweep = await _sweep_repo.get_sweep(session, sid)
        if sweep is None:
            raise NotFoundError(f"Sweep '{sweep_id_str}' not found.")
        tag = await session.get(TagModel, sweep.tag_id)
        resolved = tag.name if tag is not None else "unknown"
        return ResolvedSweepForStatus(sweep=sweep, tag_name=resolved)

    tag_model = await _tag_repo.get_tag_model(session, tag_name_str)
    if tag_model is None:
        raise NotFoundError(f"Tag '{tag_name_str}' not found.")
    sweep = await _sweep_repo.get_sweep_for_tag(session, tag_model.id)
    if sweep is None:
        raise NotFoundError(f"No sweep run recorded for tag '{tag_model.name}'.")
    return ResolvedSweepForStatus(sweep=sweep, tag_name=tag_model.name)


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


def register_sweep_tools(app_mcp: AppMcp) -> None:
    """Register sweep MCP tools and UI resource."""

    @app_mcp.mcp.resource(_SWEEP_RESOURCE_URI, name="sweep_ui", mime_type=_UI_MIME_TYPE)
    def sweep_ui() -> str:
        return _read_ui("pages/sweep.html")

    @app_mcp.tool(
        name="enqueue_tag_sweep",
        description=(
            "Trigger an async sweep that evaluates eligible cards against the tag description "
            "and applies the tag to matches. "
            "Always ask the user how many cards to sweep (limit) before calling this tool — "
            "do not assume or infer a value."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": _SWEEP_RESOURCE_URI}},
    )
    async def enqueue_tag_sweep(
        tag_name: Annotated[str, Field(description="Tag name to sweep (must exist).")],
        limit: Annotated[
            int,
            Field(
                description=(
                    "Number of cards to sweep. Must be explicitly provided by the user — "
                    "do not default or infer this value. "
                    "0 means the entire eligible catalog (can be tens of thousands of cards)."
                ),
                ge=0,
            ),
        ],
        audit_after: Annotated[
            bool,
            Field(description="Run an audit sweep automatically after processing completes."),
        ] = True,
    ) -> SweepEnqueueResult:
        request = SweepKickoffRequest(
            tag_name=tag_name,
            include_unsure=True,
            include_excluded=True,
            audit_after=audit_after,
        )
        async with app_mcp.session() as session:
            sweep = await _sweep_initializer.init_sweep(session, request)
            sweep_id = sweep.id

        enqueue_materialize_sweep_batches(
            str(sweep_id),
            tag_name,
            limit=limit,
            reenqueue_failed=False,
        )
        return SweepEnqueueResult(sweep_id=str(sweep_id))

    @app_mcp.tool(
        name="get_sweep_status",
        description=(
            "Return the current status of a tag sweep run. "
            "Provide exactly one of sweep_id (from enqueue_tag_sweep) or tag_name."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": _SWEEP_RESOURCE_URI}},
    )
    async def get_sweep_status(
        sweep_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Sweep run UUID from enqueue_tag_sweep. Mutually exclusive with tag_name."
                ),
            ),
        ] = None,
        tag_name: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Tag name (canonical); resolves that tag's sweep row. "
                    "Mutually exclusive with sweep_id."
                ),
            ),
        ] = None,
    ) -> SweepStatusResponse:
        sweep_id_str = (sweep_id or "").strip()
        tag_name_str = (tag_name or "").strip()
        if bool(sweep_id_str) == bool(tag_name_str):
            raise InvalidRequestError("Provide exactly one of sweep_id or tag_name (non-empty).")

        async with app_mcp.session() as session:
            resolved = await _resolve_sweep_for_status_query(
                session,
                sweep_id_str=sweep_id_str,
                tag_name_str=tag_name_str,
            )
            sweep = resolved.sweep
            resolved_tag_name = resolved.tag_name
            batches = await _sweep_repo.get_batches(session, sweep.id)
            audit_model = None
            if sweep.post_sweep_audit_id is not None:
                audit_model = await _audit_repo.get_audit(session, sweep.post_sweep_audit_id)

        # Batch count bucketing
        pending = sum(1 for b in batches if b.batch.status == BatchStatus.PENDING_SUBMIT)
        submitted = sum(
            1
            for b in batches
            if b.batch.status
            in {BatchStatus.SUBMITTED, BatchStatus.IN_PROGRESS, BatchStatus.CANCELING}
        )
        complete = sum(
            1 for b in batches if b.batch.status in {BatchStatus.ENDED, BatchStatus.PROCESSED}
        )
        failed_batches = sum(1 for b in batches if b.batch.status in FAILED_BATCH_STATUSES)

        # Audit status derivation
        audit: AuditStatus | None = None
        audit_status: AuditStatusValue | None = None
        if audit_model is not None:
            if audit_model.batch_id is None:
                audit_status = "pending"
            elif audit_model.report is not None:
                audit_status = "complete"
            elif (
                audit_model.batch is not None and audit_model.batch.status in FAILED_BATCH_STATUSES
            ):
                audit_status = "failed"
            else:
                audit_status = "in_progress"
            audit = AuditStatus(
                audit_id=str(audit_model.id),
                status=audit_status,
                report=audit_model.report,
            )

        # Overall status derivation
        overall: SweepStatusValue
        if sweep.status == SweepRunStatus.FAILED:
            overall = "failed"
        elif sweep.status == SweepRunStatus.OPEN:
            overall = "pending" if (pending + submitted) > 0 else "open"
        else:
            # sweep complete
            if audit is None or audit_status == "complete":
                overall = "complete"
            elif audit_status == "failed":
                overall = "failed"
            else:
                overall = "auditing"

        return SweepStatusResponse(
            sweep_id=str(sweep.id),
            tag_name=resolved_tag_name,
            status=overall,
            triggered_at=sweep.triggered_at.isoformat(),
            completed_at=sweep.completed_at.isoformat() if sweep.completed_at else None,
            batch_counts=BatchCounts(
                total=len(batches),
                pending=pending,
                submitted=submitted,
                complete=complete,
                failed=failed_batches,
            ),
            audit=audit,
        )
