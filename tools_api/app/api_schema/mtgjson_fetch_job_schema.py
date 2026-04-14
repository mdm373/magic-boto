"""Structured MCP responses for MTGJSON async fetch jobs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MtgjsonFetchEditionLine(BaseModel):
    """One edition row within a fetch job (poll payload)."""

    set_code: str
    state: Literal["requested", "inprogress", "done"]
    started_at: str | None = None
    ended_at: str | None = None
    updated_cards_count: int = Field(ge=0)


class MtgjsonFetchJobStatusResponse(BaseModel):
    """Current job state for ``get_mtgjson_fetch_job``."""

    job_id: str
    started_at: str | None = None
    ended_at: str | None = None
    error_message: str | None = None
    editions: list[MtgjsonFetchEditionLine] = Field(default_factory=list)


class EnqueueMtgjsonFetchResponse(BaseModel):
    """Result of ``enqueue_mtgjson_fetch``."""

    status: Literal["ok"] = "ok"
    job_id: str


class OpenMtgjsonFetchUiResponse(BaseModel):
    """Result of ``open_mtgjson_fetch_ui`` (opens MCP App only; does not start a job)."""

    ready: Literal[True] = True


__all__ = [
    "EnqueueMtgjsonFetchResponse",
    "MtgjsonFetchEditionLine",
    "MtgjsonFetchJobStatusResponse",
    "OpenMtgjsonFetchUiResponse",
]
