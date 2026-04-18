"""Structured MCP responses for MTGJSON async fetch jobs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MtgjsonFetchEditionLine(BaseModel):
    """Per-edition state inside a fetch job."""

    set_code: str
    state: Literal["requested", "inprogress", "done"]
    started_at: str | None = None
    ended_at: str | None = None
    updated_cards_count: int = Field(ge=0)


class MtgjsonFetchJobStatusResponse(BaseModel):
    """Job row plus edition lines for polling."""

    job_id: str
    started_at: str | None = None
    ended_at: str | None = None
    error_message: str | None = None
    editions: list[MtgjsonFetchEditionLine] = Field(default_factory=list)


class EnqueueMtgjsonFetchResponse(BaseModel):
    """Job id returned after enqueueing a fetch."""

    status: Literal["ok"] = "ok"
    job_id: str


class OpenMtgjsonFetchUiResponse(BaseModel):
    """Handshake payload for ``begin_mtgjson_fetch``."""

    ready: Literal[True] = True


__all__ = [
    "EnqueueMtgjsonFetchResponse",
    "MtgjsonFetchEditionLine",
    "MtgjsonFetchJobStatusResponse",
    "OpenMtgjsonFetchUiResponse",
]
