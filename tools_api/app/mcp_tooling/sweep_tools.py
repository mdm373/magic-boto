"""MCP sweep tool registrations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from loguru import logger
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema.audit_schema import AuditStatus, AuditStatusValue
from app.api_schema.sweep_schema import (
    BatchCounts,
    CleanTagSweepResetResult,
    GlobalSweepCatchupResult,
    GlobalSweepCatchupTagResult,
    SweepEnqueueResult,
    SweepListResponse,
    SweepListRow,
    SweepStatusResponse,
    SweepStatusValue,
)
from app.errors import InvalidRequestError, NotFoundError
from app.models import FAILED_BATCH_STATUSES, BatchStatus, SweepRunStatus, TagModel, TagSweepModel
from app.repository import TagAuditRepo, TagRepo, TagSweepRepo
from app.services import create_tag_sweep_reset_service
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
_SWEEP_CATCHUP_RESOURCE_URI = "ui://magic-boto/sweep-catchup"
# Same semantics as ``enqueue_tag_sweep``: 0 = all incremental-eligible cards per tag.
_GLOBAL_SWEEP_CATCHUP_CARD_LIMIT = 0

_sweep_repo = TagSweepRepo()
_audit_repo = TagAuditRepo()
_tag_repo = TagRepo()
_sweep_initializer = create_tag_sweep_initializer()
_sweep_reset_service = create_tag_sweep_reset_service()


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


async def _build_sweep_status_response(
    session: AsyncSession,
    *,
    sweep: TagSweepModel,
    tag_name: str,
) -> SweepStatusResponse:
    """Batch counts, audit slice, and overall status for one sweep (shared list/get)."""
    batches = await _sweep_repo.get_batches(session, sweep.id)
    audit_model = None
    if sweep.post_sweep_audit_id is not None:
        audit_model = await _audit_repo.get_audit(session, sweep.post_sweep_audit_id)

    pending = sum(1 for b in batches if b.batch.status == BatchStatus.PENDING_SUBMIT)
    submitted = sum(
        1
        for b in batches
        if b.batch.status in {BatchStatus.SUBMITTED, BatchStatus.IN_PROGRESS, BatchStatus.CANCELING}
    )
    complete = sum(
        1 for b in batches if b.batch.status in {BatchStatus.ENDED, BatchStatus.PROCESSED}
    )
    failed_batches = sum(1 for b in batches if b.batch.status in FAILED_BATCH_STATUSES)

    audit: AuditStatus | None = None
    audit_status: AuditStatusValue | None = None
    if audit_model is not None:
        if audit_model.batch_id is None:
            audit_status = "pending"
        elif audit_model.report is not None:
            audit_status = "complete"
        elif audit_model.batch is not None and audit_model.batch.status in FAILED_BATCH_STATUSES:
            audit_status = "failed"
        else:
            audit_status = "in_progress"
        audit = AuditStatus(
            audit_id=str(audit_model.id),
            status=audit_status,
            report=audit_model.report,
        )

    overall: SweepStatusValue
    if sweep.status == SweepRunStatus.FAILED:
        overall = "failed"
    elif sweep.status == SweepRunStatus.OPEN:
        overall = "pending" if (pending + submitted) > 0 else "open"
    else:
        if audit is None or audit_status == "complete":
            overall = "complete"
        elif audit_status == "failed":
            overall = "failed"
        else:
            overall = "auditing"

    return SweepStatusResponse(
        sweep_id=str(sweep.id),
        tag_name=tag_name,
        status=overall,
        requested_limit=sweep.requested_limit,
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


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


def register_sweep_tools(app_mcp: AppMcp) -> None:
    """Register sweep MCP tools and UI resource."""

    @app_mcp.mcp.resource(_SWEEP_RESOURCE_URI, name="sweep_ui", mime_type=_UI_MIME_TYPE)
    def sweep_ui() -> str:
        return _read_ui("pages/sweep.html")

    @app_mcp.mcp.resource(
        _SWEEP_CATCHUP_RESOURCE_URI, name="sweep_catchup_ui", mime_type=_UI_MIME_TYPE
    )
    def sweep_catchup_ui() -> str:
        return _read_ui("pages/sweep-catchup.html")

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
            sweep = await _sweep_initializer.init_sweep(
                session,
                request,
                requested_limit=limit,
            )
            sweep_id = sweep.id
            await session.commit()

        enqueue_materialize_sweep_batches(
            str(sweep_id),
            tag_name,
            limit=limit,
            reenqueue_failed=False,
        )
        return SweepEnqueueResult(sweep_id=str(sweep_id))

    @app_mcp.tool(
        name="clean_reset_tag_sweep",
        description=(
            "Full reset before a new sweep for a tag: removes all ``card_tags`` for the tag "
            "and its ``_unsure`` / ``_excluded`` side tags (then deletes those side tag rows), "
            "deletes all ``tag_audit`` rows for the tag (and their linked batches), "
            "deletes sweep batch history, clears the sweep epoch gate, and removes any open "
            "sweep run. Does not change the main tag description. Then call enqueue_tag_sweep."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def clean_reset_tag_sweep(
        tag_name: Annotated[
            str,
            Field(description="Tag name to clean (main tag must exist)."),
        ],
    ) -> CleanTagSweepResetResult:
        name = tag_name.strip()
        async with app_mcp.session() as session:
            result = await _sweep_reset_service.clean_reset_for_new_sweep(session, name)
        return CleanTagSweepResetResult(
            tag_name=name,
            deleted_sweep_id=result.deleted_sweep_id,
            cards_cleared=result.cards_cleared,
            batches_deleted=result.batches_deleted,
        )

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
            return await _build_sweep_status_response(
                session,
                sweep=resolved.sweep,
                tag_name=resolved.tag_name,
            )

    @app_mcp.tool(
        name="list_sweeps",
        description=(
            "List status for every tag that has a recorded tag sweep (``tag_sweep`` row). "
            "Read-only; use from the sweep-catchup status UI to poll progress."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": _SWEEP_CATCHUP_RESOURCE_URI}},
    )
    async def list_sweeps() -> SweepListResponse:
        async with app_mcp.session() as session:
            stmt = (
                select(TagSweepModel, TagModel.name)
                .join(TagModel, TagSweepModel.tag_id == TagModel.id)
                .order_by(TagModel.name.asc())
            )
            pairs = (await session.execute(stmt)).all()
            rows: list[SweepListRow] = []
            for sweep, name in pairs:
                status_row = await _build_sweep_status_response(session, sweep=sweep, tag_name=name)
                rows.append(SweepListRow.model_validate(status_row.model_dump()))
            return SweepListResponse(rows=rows)

    @app_mcp.tool(
        name="enqueue_global_sweep_catchup",
        description=(
            "For every tag that already has a ``tag_sweep`` row: prune ``_unsure`` / ``_excluded`` "
            "side tags, all audits, and prior sweep batch rows; then reopen/init the sweep with "
            "``audit_after=false``, ``include_unsure=false``, ``include_excluded=false`` (no new "
            "side tags during processing), and enqueue Celery materialization for the **entire** "
            "incremental-eligible catalog per tag (same as ``limit=0`` on ``enqueue_tag_sweep``). "
            "Opens the read-only sweep-catchup status UI via tool meta."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": _SWEEP_CATCHUP_RESOURCE_URI}},
    )
    async def enqueue_global_sweep_catchup() -> GlobalSweepCatchupResult:
        async with app_mcp.session() as session:
            stmt = (
                select(TagModel.name)
                .join(TagSweepModel, TagSweepModel.tag_id == TagModel.id)
                .order_by(TagModel.name.asc())
            )
            tag_names = list((await session.execute(stmt)).scalars().all())

        tags_out: list[GlobalSweepCatchupTagResult] = []
        enqueued_count = 0
        skipped_count = 0

        for tag_name in tag_names:
            async with app_mcp.session() as session:
                await _sweep_reset_service.prune_side_tags_audits_and_sweep_batches(
                    session, tag_name
                )
                request = SweepKickoffRequest(
                    tag_name=tag_name,
                    include_unsure=False,
                    include_excluded=False,
                    audit_after=False,
                )
                sweep = await _sweep_initializer.init_sweep(
                    session,
                    request,
                    requested_limit=_GLOBAL_SWEEP_CATCHUP_CARD_LIMIT,
                )
                sweep_id = sweep.id
                await session.commit()
                tag_m = await _tag_repo.require_tag_model(session, tag_name)
                eligible = await _sweep_repo.fetch_eligible_oracle_ids(
                    session,
                    tag_m,
                    sweep_id,
                    _GLOBAL_SWEEP_CATCHUP_CARD_LIMIT,
                )

            if not eligible:
                tags_out.append(
                    GlobalSweepCatchupTagResult(
                        tag_name=tag_name,
                        sweep_id=str(sweep_id),
                        enqueued=False,
                        error="No eligible cards to sweep",
                    )
                )
                skipped_count += 1
                logger.info("Global sweep catch-up: skipped {} (no eligible cards).", tag_name)
                continue

            enqueue_materialize_sweep_batches(
                str(sweep_id),
                tag_name,
                limit=_GLOBAL_SWEEP_CATCHUP_CARD_LIMIT,
                reenqueue_failed=False,
            )
            tags_out.append(
                GlobalSweepCatchupTagResult(
                    tag_name=tag_name,
                    sweep_id=str(sweep_id),
                    enqueued=True,
                    error=None,
                )
            )
            enqueued_count += 1

        return GlobalSweepCatchupResult(
            tags_considered=len(tag_names),
            enqueued_count=enqueued_count,
            skipped_count=skipped_count,
            tags=tags_out,
        )
