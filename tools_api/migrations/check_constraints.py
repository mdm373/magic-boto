from __future__ import annotations

from collections.abc import Sequence

from alembic import op


def _sql_literal(value: str) -> str:
    """Return a SQL string literal with single quotes escaped."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _allowed_values_check_clause(column: str, values: Sequence[str], *, allow_null: bool) -> str:
    if not values:
        raise ValueError("values must be a non-empty sequence")

    column_sql = f'"{column}"'
    values_sql = ", ".join(_sql_literal(v) for v in values)
    in_list = f"{column_sql} IN ({values_sql})"
    if allow_null:
        return f"{column_sql} IS NULL OR {in_list}"
    return f"{column_sql} IS NOT NULL AND {in_list}"


def create_allowed_values_check_constraint(
    *,
    schema: str,
    table: str,
    column: str,
    values: Sequence[str],
    allow_null: bool = False,
) -> None:
    """
    Create a check constraint that restricts a column to a fixed allowed set.

    By default NULL is **not** allowed (uses ``IS NOT NULL AND col IN (...)``).

    Constraint name convention: ``schema_table_column_av``.
    """

    name = f"{schema}_{table}_{column}_av"
    clause = _allowed_values_check_clause(column, values, allow_null=allow_null)
    op.create_check_constraint(name, table, clause, schema=schema)


def drop_allowed_values_check_constraint(
    *,
    schema: str,
    table: str,
    column: str,
) -> None:
    """Drop the check constraint created by ``create_allowed_values_check_constraint``."""

    name = f"{schema}_{table}_{column}_av"
    op.drop_constraint(name, table, schema=schema, type_="check")
