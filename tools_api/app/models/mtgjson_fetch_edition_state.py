"""Allowed ``mtgjson_fetch_job_editions.state`` values."""

from __future__ import annotations

from enum import StrEnum


class MtgjsonFetchEditionState(StrEnum):
    """Edition row lifecycle for one set within one fetch job."""

    REQUESTED = "requested"
    INPROGRESS = "inprogress"
    DONE = "done"


__all__ = ["MtgjsonFetchEditionState"]
