"""Canonical form for ``magic_boto.inventories.name`` (trim + lowercase)."""

DEFAULT_INVENTORY_NAME = "_default"


def canonical_inventory_name(name: str) -> str:
    """Trim and lowercase for storage and lookup."""
    return name.strip().lower()
