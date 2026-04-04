"""MTGJSON edition (set) response and query schemas."""

from pydantic import BaseModel, Field


class EditionsQuery(BaseModel):
    """Query params for listing editions (extensible)."""

    set_code: str | None = Field(
        default=None,
        min_length=1,
        description="Exact edition/set code (e.g. M21).",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        description="Fuzzy search on edition name (case-insensitive substring).",
    )

    def is_empty(self) -> bool:
        """True if no filter is set."""
        return self.set_code is None and self.name is None


class Edition(BaseModel):
    """MTGJSON edition (set) for API responses."""

    set_code: str = Field(..., min_length=1, description="Edition/set code (e.g. M21)")
    name: str = Field("", description="Edition/set display name")
