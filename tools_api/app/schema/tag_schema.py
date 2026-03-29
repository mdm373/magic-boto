"""Pydantic schemas for tags."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """A user-defined tag that can be applied to cards."""

    name: str = Field(description="Canonical (lowercase, trimmed) tag name.")
    description: str = Field(description="Human-readable description of the tag's intent.")


class CreateTagRequest(BaseModel):
    name: str = Field(description="Tag name. Stored trimmed and lowercased.")
    description: str = Field(description="Description of the tag's intent.")


class CardTagRequest(BaseModel):
    scryfall_ids: list[str] = Field(
        description=(
            "Scryfall printing IDs of the cards to tag or untag. "
            "The tag is applied to the oracle identity of each printing, "
            "so all printings of the same card are covered by a single tag."
        )
    )
