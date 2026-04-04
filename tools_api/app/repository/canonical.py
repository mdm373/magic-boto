"""Shared name normalization for repository lookups."""


def canonical_name(name: str) -> str:
    """Trim and lowercase a name for storage and lookup."""
    return name.strip().lower()
