"""SQLAlchemy Enum mapped to DB text (no native PG enum); pair with CHECK constraints."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=Enum)


def text_enum(enum_cls: type[E]) -> SAEnum:
    """
    Build a SQLAlchemy Enum that stores enum **values** as plain text.

    Use when the database column is ``text``/``varchar`` and optional CHECK
    constraints define the allowed set (no PostgreSQL ``ENUM`` type).
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda x: [e.value for e in x],
    )
