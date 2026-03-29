"""Pydantic schemas for tags."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """A user-defined tag that can be applied to cards."""

    name: str = Field(description="Canonical (lowercase, trimmed) tag name.")
    description: str = Field(description="Human-readable description of the tag's intent.")
