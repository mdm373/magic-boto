"""MCP audit tool registrations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import Field

from app.api_schema.audit_schema import ApplyAuditResult, AuditResponse, AuditStatusValue
from app.errors import InvalidRequestError, NotFoundError
from app.models import FAILED_BATCH_STATUSES
from app.repository import TagAuditRepo, TagRepo
from app.services import create_tag_audit_apply_service, create_tag_sweep_reset_service

from .error_middleware import AppMcp

_AUDIT_RESOURCE_URI = "ui://magic-boto/audit"
_UI_DIST = Path(__file__).parent / "ui_dist"
_UI_MIME_TYPE = "text/html;profile=mcp-app"
_FALLBACK_HTML = (
    "<!doctype html><html><body style='font-family:sans-serif;padding:1rem'>"
    "<p>UI not built. Run <code>npm run build</code> inside "
    "<code>tools-ui/</code>.</p></body></html>"
)

_apply_service = create_tag_audit_apply_service()
_reset_service = create_tag_sweep_reset_service()
_audit_repo = TagAuditRepo()
_tag_repo = TagRepo()


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


def register_audit_tools(app_mcp: AppMcp) -> None:
    """Register audit MCP tools and UI resource."""

    @app_mcp.mcp.resource(_AUDIT_RESOURCE_URI, name="audit_ui", mime_type=_UI_MIME_TYPE)
    def audit_ui() -> str:
        return _read_ui("pages/audit.html")

    @app_mcp.tool(
        name="get_tag_audit",
        description=(
            "Return an audit by ID or the latest audit for a tag by name. "
            "Provide exactly one of audit_id or tag_name."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": _AUDIT_RESOURCE_URI}},
    )
    async def get_tag_audit(
        audit_id: Annotated[
            str | None,
            Field(default=None, description="Audit UUID. Mutually exclusive with tag_name."),
        ] = None,
        tag_name: Annotated[
            str | None,
            Field(
                default=None,
                description="Tag name; uses latest audit. Mutually exclusive with audit_id.",
            ),
        ] = None,
    ) -> AuditResponse:
        audit_id_str = (audit_id or "").strip()
        tag_name_str = (tag_name or "").strip()
        if bool(audit_id_str) == bool(tag_name_str):
            raise InvalidRequestError("Provide exactly one of audit_id or tag_name (non-empty).")

        async with app_mcp.session() as session:
            if audit_id_str:
                try:
                    aid = uuid.UUID(audit_id_str)
                except ValueError as e:
                    raise InvalidRequestError(f"Invalid audit_id {audit_id_str!r}.") from e
                audit = await _audit_repo.get_audit(session, aid)
                if audit is None:
                    raise NotFoundError(f"Audit '{audit_id_str}' not found.")
                tag = await _tag_repo.get_tag_model_by_id(session, audit.tag_id)
                resolved_tag_name = tag.name if tag is not None else "unknown"
            else:
                tag = await _tag_repo.get_tag_model(session, tag_name_str)
                if tag is None:
                    raise NotFoundError(f"Tag '{tag_name_str}' not found.")
                audit = await _audit_repo.get_latest_for_tag(session, tag.id)
                if audit is None:
                    raise NotFoundError(f"No audit found for tag '{tag_name_str}'.")
                resolved_tag_name = tag_name_str

            audit_status: AuditStatusValue
            if audit.batch_id is None:
                audit_status = "pending"
            elif audit.report is not None:
                audit_status = "complete"
            elif audit.batch is not None and audit.batch.status in FAILED_BATCH_STATUSES:
                audit_status = "failed"
            else:
                audit_status = "in_progress"

            return AuditResponse(
                audit_id=str(audit.id),
                tag_name=resolved_tag_name,
                status=audit_status,
                report=audit.report,
                suggestion=audit.suggestion,
                triggered_at=audit.triggered_at.isoformat(),
            )

    @app_mcp.tool(
        name="apply_audit",
        description=(
            "Apply the latest completed audit to a tag: updates the tag description from the "
            "audit suggestion, clears all tagged cards and side tags, resets the sweep epoch, "
            "and deletes any open sweep run."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def apply_audit(
        tag_name: Annotated[str, Field(description="Tag name to apply the audit to.")],
        delete_tagged: Annotated[
            bool,
            Field(description="Delete all card_tag entries for the tag."),
        ] = True,
        delete_side_tags: Annotated[
            bool,
            Field(description="Delete the _unsure and _excluded side tags entirely."),
        ] = True,
    ) -> ApplyAuditResult:
        async with app_mcp.session() as session:
            result = await _apply_service.apply(
                session,
                tag_name,
                delete_tagged=delete_tagged,
                delete_side_tags=delete_side_tags,
            )
            sweep_result = await _reset_service.delete_open_sweep(session, tag_name)

        return ApplyAuditResult(
            tag_name=tag_name,
            new_description=result.new_description,
            cards_cleared=result.cards_cleared,
            sweep_reset=sweep_result.deleted_sweep_id is not None,
        )
