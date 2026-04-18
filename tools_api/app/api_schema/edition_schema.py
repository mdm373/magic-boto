"""MTGJSON edition (set) response and query schemas."""

from pydantic import BaseModel, Field


class EditionsQuery(BaseModel):
    """Filters for listing editions."""

    set_code: str | None = Field(
        default=None,
        min_length=1,
        description="Exact set code (e.g. M21).",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        description="Case-insensitive substring on edition name.",
    )

    def is_empty(self) -> bool:
        """True if no filter is set."""
        return self.set_code is None and self.name is None


class Edition(BaseModel):
    """One edition (set) row."""

    set_code: str = Field(..., min_length=1, description="Set code (e.g. M21).")
    name: str = Field("", description="Display name.")
