"""Pydantic schemas for tags."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """User-defined tag metadata."""

    name: str = Field(description="Canonical tag name (lowercase, trimmed).")
    description: str = Field(description="What the tag means for sweeps and tagging.")
    sweep_include_types: Sequence[str] = Field(
        default=(),
        description="Sweep only these card types; empty = no type restriction.",
    )
    sweep_include_supertypes: Sequence[str] = Field(
        default=(),
        description="Sweep only these supertypes; empty = no supertype restriction.",
    )


class CreateTagRequest(BaseModel):
    name: str = Field(description="Tag name (stored trimmed, lowercased).")
    description: str = Field(description="Tag intent / sweep guidance text.")
    sweep_include_types: Sequence[str] = Field(
        default=(),
        description="Restrict sweeps to these card types; empty = all types.",
    )
    sweep_include_supertypes: Sequence[str] = Field(
        default=(),
        description="Restrict sweeps to these supertypes; empty = all.",
    )


class CardTagRequest(BaseModel):
    oracle_ids: list[str] = Field(description="Oracle ids to tag or untag.")
