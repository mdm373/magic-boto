"""Schema/OpenAPI description text (e.g. enum allowed values for Query params)."""

from enum import Enum


def allowed_values_description(enum_cls: type[Enum]) -> str:
    """Return 'Allowed: v1, v2, ...' for enum values (for Query/OpenAPI descriptions)."""
    values = [e.value for e in enum_cls]
    return f"Allowed: {', '.join(values)}."
