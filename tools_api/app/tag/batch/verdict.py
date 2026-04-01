"""Verdict enum for batch sweep responses."""

from __future__ import annotations

from enum import StrEnum


class Verdict(StrEnum):
    TAG = "tag"
    UNSURE = "unsure"
    EXCLUDE = "exclude"
