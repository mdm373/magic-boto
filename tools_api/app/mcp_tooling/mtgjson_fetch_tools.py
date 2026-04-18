"""MCP tools for async MTGJSON catalog fetch (Celery + DB job rows)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, cast

from mcp.types import ToolAnnotations
from pydantic import Field

from app.api_schema.mtgjson_fetch_job_schema import (
    EnqueueMtgjsonFetchResponse,
    MtgjsonFetchEditionLine,
    MtgjsonFetchJobStatusResponse,
    OpenMtgjsonFetchUiResponse,
)
from app.errors import InvalidRequestError, NotFoundError
from app.repository.mtgjson_fetch_job_repo import MtgjsonFetchJobRepo
from app.services.mtgjson_fetch.fetch_run import parse_always_refresh_set_codes
from app.worker import enqueue_process_mtgjson_fetch_job

from .error_middleware import AppMcp

_UI_DIST = Path(__file__).parent / "ui_dist"
_UI_MIME_TYPE = "text/html;profile=mcp-app"
_FALLBACK_HTML = (
    "<!doctype html><html><body style='font-family:sans-serif;padding:1rem'>"
    "<p>UI not built. Run <code>npm run build</code> inside "
    "<code>tools-ui/</code>.</p></body></html>"
)
_FETCH_UI_URI = "ui://magic-boto/mtgjson-fetch"

_repo = MtgjsonFetchJobRepo()


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def register_mtgjson_fetch_tools(app_mcp: AppMcp) -> None:
    """Register MTGJSON fetch MCP tools and bundled UI resource."""

    @app_mcp.mcp.resource(_FETCH_UI_URI, name="mtgjson_fetch_ui", mime_type=_UI_MIME_TYPE)
    def mtgjson_fetch_ui() -> str:
        return _read_ui("pages/mtgjson-fetch.html")

    @app_mcp.tool(
        name="begin_mtgjson_fetch",
        description="Return ``{ready: true}`` as the fetch-job tool bundle entrypoint.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": _FETCH_UI_URI}},
    )
    async def begin_mtgjson_fetch() -> OpenMtgjsonFetchUiResponse:
        return OpenMtgjsonFetchUiResponse()

    @app_mcp.tool(
        name="enqueue_ui_triggered_mtgjson_fetch",
        description=(
            "Create an MTGJSON fetch job from comma-separated set codes "
            "(empty → SLD) and enqueue processing."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def enqueue_ui_triggered_mtgjson_fetch(
        requested_set_codes: Annotated[
            str,
            Field(
                default="",
                description="Comma-separated set codes to fetch (empty uses SLD).",
            ),
        ] = "",
    ) -> EnqueueMtgjsonFetchResponse:
        raw = requested_set_codes.strip()
        if not raw:
            raw = "SLD"
        try:
            codes = parse_always_refresh_set_codes(raw)
        except ValueError as exc:
            raise InvalidRequestError(str(exc)) from exc
        async with app_mcp.session() as session:
            job_id = await _repo.create_job_with_requested_editions(session, set_codes=codes)
        enqueue_process_mtgjson_fetch_job(str(job_id))
        return EnqueueMtgjsonFetchResponse(job_id=str(job_id))

    @app_mcp.tool(
        name="get_mtgjson_fetch_job",
        description="Fetch job status and per-edition rows; poll until ``ended_at`` is set.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_mtgjson_fetch_job(
        job_id: Annotated[
            str,
            Field(description="Job UUID from ``enqueue_ui_triggered_mtgjson_fetch``."),
        ],
    ) -> MtgjsonFetchJobStatusResponse:
        from uuid import UUID

        try:
            jid = UUID(job_id.strip())
        except ValueError as exc:
            raise InvalidRequestError(f"Invalid job_id {job_id!r}.") from exc
        async with app_mcp.session() as session:
            bundle = await _repo.load_job_with_editions(session, jid)
        if bundle is None:
            raise NotFoundError(f"MTGJSON fetch job '{job_id}' not found.")
        job = bundle.job
        lines = [
            MtgjsonFetchEditionLine(
                set_code=e.set_code,
                state=cast(Literal["requested", "inprogress", "done"], e.state),
                started_at=_iso(e.started_at),
                ended_at=_iso(e.ended_at),
                updated_cards_count=e.updated_cards_count,
            )
            for e in bundle.editions
        ]
        return MtgjsonFetchJobStatusResponse(
            job_id=str(job.id),
            started_at=_iso(job.started_at),
            ended_at=_iso(job.ended_at),
            error_message=job.error_message,
            editions=lines,
        )
