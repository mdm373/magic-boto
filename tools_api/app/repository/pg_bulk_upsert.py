"""Postgres bulk insert with ``ON CONFLICT DO NOTHING`` (shared by magic_boto repos)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


def orm_columns_dict(instance: object) -> dict[str, object]:
    """Column names and values for a mapped instance (for Core ``INSERT``).

    Omits ``None`` for non-nullable columns that define ``server_default`` so the
    database default applies (explicit ``NULL`` in bulk ``INSERT`` would otherwise
    violate ``NOT NULL``).
    """
    insp = sa_inspect(instance)
    if insp is None:
        raise TypeError(f"Expected a SQLAlchemy mapped instance, got {type(instance).__name__}")
    out: dict[str, object] = {}
    for attr in insp.mapper.column_attrs:
        key = attr.key
        val = getattr(instance, key)
        if val is None:
            col = next(iter(attr.columns))
            if col.nullable is False and col.server_default is not None:
                continue
        out[key] = val
    return out


async def bulk_insert_on_conflict_do_nothing(
    session: AsyncSession,
    *,
    batch_size: int,
    model: type[Any],
    index_elements: tuple[str, ...],
    param_rows: Sequence[Mapping[str, object]],
) -> None:
    if not param_rows:
        return
    for start in range(0, len(param_rows), batch_size):
        chunk = param_rows[start : start + batch_size]
        stmt = (
            pg_insert(model)
            .values(list(chunk))
            .on_conflict_do_nothing(index_elements=list(index_elements))
        )
        await session.execute(stmt)
