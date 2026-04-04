"""Pydantic schemas for tags."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """A user-defined tag that can be applied to cards."""

    name: str = Field(description="Canonical (lowercase, trimmed) tag name.")
    description: str = Field(description="Human-readable description of the tag's intent.")
    sweep_include_types: Sequence[str] = Field(
        default=(),
        description=(
            "Card types the sweep is restricted to (e.g. 'creature', 'artifact'). "
            "Empty means all types are included."
        ),
    )
    sweep_include_supertypes: Sequence[str] = Field(
        default=(),
        description=(
            "Card supertypes the sweep is restricted to (e.g. 'legendary'). "
            "Empty means all supertypes are included."
        ),
    )


class CreateTagRequest(BaseModel):
    name: str = Field(description="Tag name. Stored trimmed and lowercased.")
    description: str = Field(description="Description of the tag's intent.")
    sweep_include_types: Sequence[str] = Field(
        default=(),
        description=(
            "Card types to restrict the sweep to (e.g. ['creature', 'artifact']). "
            "Omit or pass empty to sweep all card types."
        ),
    )
    sweep_include_supertypes: Sequence[str] = Field(
        default=(),
        description=(
            "Card supertypes to restrict the sweep to (e.g. ['legendary']). "
            "Omit or pass empty to sweep all supertypes."
        ),
    )


class CardTagRequest(BaseModel):
    oracle_ids: list[str] = Field(description="Oracle IDs of the cards to tag or untag.")
