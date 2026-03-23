"""DB maintenance tasks.

These tasks intentionally shell out to Postgres CLI tools (`psql`, `pg_dump`) to keep behavior
aligned with existing PowerShell scripts while centralizing ownership under tools_api.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import cast

from invoke import Collection, Context, Exit, task
from invoke.runners import Result
from sqlalchemy import Column, MetaData, String, Table, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncConnection

from .pg_env import pg_env

# Must match card_types check constraint and app.models.card_type.CardType.
_ALLOWED_CARD_TYPES: frozenset[str] = frozenset(
    {
        "artifact",
        "battle",
        "conspiracy",
        "creature",
        "dungeon",
        "enchantment",
        "instant",
        "kindred",
        "land",
        "phenomenon",
        "plane",
        "planeswalker",
        "scheme",
        "sorcery",
        "vanguard",
    }
)

_MTGJSON_CARD_TYPES = Table(
    "card_types",
    MetaData(),
    Column("card_uuid", String),
    Column("card_type", String),
    schema="public",
)

_MTGJSON_CARD_SUBTYPES = Table(
    "card_subtypes",
    MetaData(),
    Column("card_uuid", String),
    Column("card_subtype", String),
    schema="public",
)

_CANONICAL_CARD_SUPERTYPES_BY_LOWER: dict[str, str] = {
    "basic": "Basic",
    "host": "Host",
    "legendary": "Legendary",
    "ongoing": "Ongoing",
    "snow": "Snow",
    "world": "World",
}
_ALLOWED_CARD_SUPERTYPES_LOWER: frozenset[str] = frozenset(
    _CANONICAL_CARD_SUPERTYPES_BY_LOWER.keys()
)

_MTGJSON_CARD_SUPERTYPES = Table(
    "card_supertypes",
    MetaData(),
    Column("card_uuid", String),
    Column("card_supertype", String),
    schema="public",
)


def _split_mtgjson_csv_tokens(raw: str) -> list[str]:
    """
    Split MTGJSON list-ish fields stored as TEXT into normalized tokens.

    Expected input examples:
    - "Human, Wizard"
    - "[\"Human\",\"Wizard\"]"
    - "Human"
    """
    cleaned = re.sub(r'[\[\]"]', "", str(raw))
    tokens: list[str] = []
    for token_raw in cleaned.split(","):
        token = token_raw.strip().lower()
        if not token:
            continue
        tokens.append(token)
    return tokens


def _psql_tac(
    c: Context,
    *,
    env: dict[str, str],
    sql: str,
    hide: bool = True,
    warn: bool = True,
) -> Result:
    """Run a SQL statement via `psql -tAc`, with safe quoting.

    Uses JSON quoting to avoid hand-escaping embedded quotes.
    """
    return cast(
        Result,
        c.run(f"psql -tAc {json.dumps(sql)}", env=env, hide=hide, warn=warn),
    )


def _db_url(env: dict[str, str]) -> str:
    user = env["PGUSER"]
    password = env["PGPASSWORD"]
    host = env["PGHOST"]
    port = env["PGPORT"]
    db = env["PGDATABASE"]
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


async def _count_cards_missing_types(conn: AsyncConnection) -> int:
    """Count cards with no rows in public.card_types."""
    total_res = await conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM mtgjson.cards c
            WHERE NOT EXISTS (
              SELECT 1
                FROM public.card_types ct
              WHERE ct.card_uuid = c.uuid
            )
            """
        )
    )
    return int(total_res.scalar_one() or 0)


async def _select_cards_missing_types_batch(
    conn: AsyncConnection,
    last_uuid: str,
    limit: int,
) -> list[tuple[str, str | None]]:
    rows_res = await conn.execute(
        text(
            """
            SELECT c.uuid, c.types
            FROM mtgjson.cards c
            WHERE c.uuid > :last_uuid
              AND NOT EXISTS (
                SELECT 1
                FROM public.card_types ct
                WHERE ct.card_uuid = c.uuid
              )
            ORDER BY c.uuid
            LIMIT :limit
            """
        ),
        {"last_uuid": last_uuid, "limit": limit},
    )
    return [(str(uuid), types) for uuid, types in rows_res.all()]


async def _insert_card_types_batch(conn: AsyncConnection, rows: list[dict[str, str]]) -> int:
    """Insert many (card_uuid, card_type) rows; skip duplicates (PK or existing)."""
    if not rows:
        return 0
    stmt = pg_insert(_MTGJSON_CARD_TYPES).values(rows).on_conflict_do_nothing()
    result = await conn.execute(stmt)
    return int(result.rowcount or 0)


async def _backfill_card_types(*, env: dict[str, str], batch_size: int) -> None:
    engine = create_async_engine(_db_url(env), pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            total = await _count_cards_missing_types(conn)
            print(f"Backfilling card_types for {total} cards (batch_size={batch_size})...")
            processed = 0
            batch_num = 0
            last_uuid = ""
            total_skipped_invalid = 0
            total_inserted = 0
            max_batches = (total + batch_size - 1) // batch_size
            for _ in range(max_batches):
                batch_num += 1
                rows = await _select_cards_missing_types_batch(conn, last_uuid, batch_size)
                if not rows:
                    continue

                last_uuid = str(rows[-1][0])
                skipped_invalid = 0
                to_insert: list[dict[str, str]] = []
                seen_keys: set[tuple[str, str]] = set()

                for card_uuid, types_raw in rows:
                    if not types_raw:
                        continue
                    for token_raw in str(types_raw).split(","):
                        token = token_raw.strip().lower()
                        if not token:
                            continue
                        if token not in _ALLOWED_CARD_TYPES:
                            skipped_invalid += 1
                            continue
                        key = (card_uuid, token)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        to_insert.append({"card_uuid": card_uuid, "card_type": token})

                inserted = await _insert_card_types_batch(conn, to_insert)

                processed += len(rows)
                total_skipped_invalid += skipped_invalid
                total_inserted += inserted
                pct = min(100.0, (processed / total) * 100.0)
                print(
                    f"Batch {batch_num}: processed={processed}/{total} ({pct:.1f}%), "
                    f"inserted_rows={inserted}, skipped_invalid_tokens={skipped_invalid}"
                )

            print(
                "Info: card_types backfill summary: "
                f"attempted_cards={processed}, inserted_rows={total_inserted}, "
                f"skipped_invalid_tokens={total_skipped_invalid}"
            )
    finally:
        await engine.dispose()


async def _count_cards_missing_subtypes(conn: AsyncConnection) -> int:
    """Count cards with no rows in public.card_subtypes."""
    total_res = await conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM mtgjson.cards c
            WHERE NOT EXISTS (
              SELECT 1
              FROM public.card_subtypes st
              WHERE st.card_uuid = c.uuid
            )
            """
        )
    )
    return int(total_res.scalar_one() or 0)


async def _select_cards_missing_subtypes_batch(
    conn: AsyncConnection,
    last_uuid: str,
    limit: int,
) -> list[tuple[str, str | None]]:
    rows_res = await conn.execute(
        text(
            """
            SELECT c.uuid, c.subtypes
            FROM mtgjson.cards c
            WHERE c.uuid > :last_uuid
              AND NOT EXISTS (
                SELECT 1
                FROM public.card_subtypes st
                WHERE st.card_uuid = c.uuid
              )
            ORDER BY c.uuid
            LIMIT :limit
            """
        ),
        {"last_uuid": last_uuid, "limit": limit},
    )
    return [(str(uuid), subtypes) for uuid, subtypes in rows_res.all()]


async def _insert_card_subtypes_batch(
    conn: AsyncConnection,
    rows: list[dict[str, str]],
) -> int:
    """Insert many (card_uuid, card_subtype) rows; skip duplicates (PK or existing)."""
    if not rows:
        return 0
    stmt = pg_insert(_MTGJSON_CARD_SUBTYPES).values(rows).on_conflict_do_nothing()
    result = await conn.execute(stmt)
    return int(result.rowcount or 0)


async def _backfill_card_subtypes(*, env: dict[str, str], batch_size: int) -> None:
    engine = create_async_engine(_db_url(env), pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            total = await _count_cards_missing_subtypes(conn)
            print(f"Backfilling card_subtypes for {total} cards (batch_size={batch_size})...")
            processed = 0
            batch_num = 0
            last_uuid = ""
            total_inserted = 0
            max_batches = (total + batch_size - 1) // batch_size
            for _ in range(max_batches):
                batch_num += 1
                rows = await _select_cards_missing_subtypes_batch(conn, last_uuid, batch_size)
                if not rows:
                    continue

                last_uuid = str(rows[-1][0])
                to_insert: list[dict[str, str]] = []
                seen_keys: set[tuple[str, str]] = set()

                for card_uuid, subtypes_raw in rows:
                    if not subtypes_raw:
                        continue
                    for token in _split_mtgjson_csv_tokens(str(subtypes_raw)):
                        key = (card_uuid, token)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        to_insert.append({"card_uuid": card_uuid, "card_subtype": token})

                inserted = await _insert_card_subtypes_batch(conn, to_insert)
                processed += len(rows)
                total_inserted += inserted

                pct = min(100.0, (processed / total) * 100.0)
                print(
                    f"Batch {batch_num}: processed={processed}/{total} ({pct:.1f}%), "
                    f"inserted_rows={inserted}"
                )

            print(
                "Info: card_subtypes backfill summary: "
                f"attempted_cards={processed}, inserted_rows={total_inserted}"
            )
    finally:
        await engine.dispose()


async def _count_cards_missing_supertypes(conn: AsyncConnection) -> int:
    """Count cards with no rows in public.card_supertypes."""
    total_res = await conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM mtgjson.cards c
            WHERE NOT EXISTS (
              SELECT 1
              FROM public.card_supertypes st
              WHERE st.card_uuid = c.uuid
            )
            """
        )
    )
    return int(total_res.scalar_one() or 0)


async def _select_cards_missing_supertypes_batch(
    conn: AsyncConnection,
    last_uuid: str,
    limit: int,
) -> list[tuple[str, str | None]]:
    rows_res = await conn.execute(
        text(
            """
            SELECT c.uuid, c.supertypes
            FROM mtgjson.cards c
            WHERE c.uuid > :last_uuid
              AND NOT EXISTS (
                SELECT 1
                FROM public.card_supertypes st
                WHERE st.card_uuid = c.uuid
              )
            ORDER BY c.uuid
            LIMIT :limit
            """
        ),
        {"last_uuid": last_uuid, "limit": limit},
    )
    return [(str(uuid), supertypes) for uuid, supertypes in rows_res.all()]


async def _insert_card_supertypes_batch(
    conn: AsyncConnection,
    rows: list[dict[str, str]],
) -> int:
    """Insert many (card_uuid, card_supertype) rows; skip duplicates (PK or existing)."""
    if not rows:
        return 0
    stmt = pg_insert(_MTGJSON_CARD_SUPERTYPES).values(rows).on_conflict_do_nothing()
    result = await conn.execute(stmt)
    return int(result.rowcount or 0)


async def _backfill_card_supertypes(*, env: dict[str, str], batch_size: int) -> None:
    engine = create_async_engine(_db_url(env), pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            total = await _count_cards_missing_supertypes(conn)
            print(f"Backfilling card_supertypes for {total} cards (batch_size={batch_size})...")
            processed = 0
            batch_num = 0
            last_uuid = ""
            total_inserted = 0
            max_batches = (total + batch_size - 1) // batch_size
            for _ in range(max_batches):
                batch_num += 1
                rows = await _select_cards_missing_supertypes_batch(conn, last_uuid, batch_size)
                if not rows:
                    continue

                last_uuid = str(rows[-1][0])
                to_insert: list[dict[str, str]] = []
                seen_keys: set[tuple[str, str]] = set()

                for card_uuid, supertypes_raw in rows:
                    if not supertypes_raw:
                        continue
                    for token in _split_mtgjson_csv_tokens(str(supertypes_raw)):
                        if token not in _ALLOWED_CARD_SUPERTYPES_LOWER:
                            continue
                        key = (card_uuid, token)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        canonical = _CANONICAL_CARD_SUPERTYPES_BY_LOWER[token]
                        to_insert.append({"card_uuid": card_uuid, "card_supertype": canonical})

                inserted = await _insert_card_supertypes_batch(conn, to_insert)
                processed += len(rows)
                total_inserted += inserted

                pct = min(100.0, (processed / total) * 100.0 if total else 100.0)
                print(
                    f"Batch {batch_num}: processed={processed}/{total} ({pct:.1f}%), "
                    f"inserted_rows={inserted}"
                )

            print(
                "Info: card_supertypes backfill summary: "
                f"attempted_cards={processed}, inserted_rows={total_inserted}"
            )
    finally:
        await engine.dispose()


def _resolve_allprintings_path() -> Path:
    raw = input("Path to AllPrintings.psql / .psql.zip / .psql.gz: ").strip().strip('"')
    if not raw:
        raise Exit("No file path entered.")
    path = Path(raw).expanduser()
    if not path.exists():
        raise Exit(f"File not found: {path}")
    return path.resolve()


def _materialize_psql_in_dir(input_path: Path, temp_dir: Path) -> Path:
    """Return a .psql path, writing any intermediates under temp_dir.

    This is designed to be used with tempfile.TemporaryDirectory() so cleanup is automatic.
    """
    suffixes = [s.lower() for s in input_path.suffixes]

    if suffixes[-1] == ".psql":
        return input_path

    if suffixes[-1] == ".zip":
        extract_dir = temp_dir / "mtgjson_extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(extract_dir)
        candidates = sorted(extract_dir.rglob("*.psql"))
        if not candidates:
            raise Exit("No .psql file found inside the zip.")
        return candidates[0]

    if suffixes[-1] == ".gz":
        out_path = temp_dir / "AllPrintings.psql"
        with gzip.open(input_path, "rb") as fin, out_path.open("wb") as fout:
            shutil.copyfileobj(fin, fout)
        return out_path

    raise Exit("Unsupported format. Use .psql, .zip, or .gz.")


def _preprocess_for_postgres(psql_path: Path, out_path: Path) -> None:
    content = psql_path.read_text(encoding="utf-8", errors="replace")
    schema_header = "CREATE SCHEMA IF NOT EXISTS mtgjson;\nSET search_path TO mtgjson;\n\n"
    content = schema_header + content

    # Upgrade INTEGER/INT to BIGINT (dump has large values that can overflow int4).
    content = re.sub(r"\bINTEGER\b", "BIGINT", content, flags=re.IGNORECASE)
    content = re.sub(r"\bINT\b", "BIGINT", content, flags=re.IGNORECASE)
    out_path.write_text(content, encoding="utf-8")


@task(default=True)
def mtg_json(c: Context) -> None:
    """Populate the DB with MTGJSON AllPrintings."""
    env = pg_env()
    probe = _psql_tac(
        c,
        env=env,
        sql="SELECT 1 FROM information_schema.schemata WHERE schema_name = 'mtgjson'",
    )
    if probe.ok and probe.stdout.strip() == "1":
        print("Info: skipping MTGJSON population (schema 'mtgjson' already exists).")
        return

    debug_dir = Path("debug")
    debug_dir.mkdir(parents=True, exist_ok=True)

    input_path = _resolve_allprintings_path()

    with tempfile.TemporaryDirectory(prefix="magicboto_mtgjson_") as td:
        temp_dir = Path(td)
        psql_path = _materialize_psql_in_dir(input_path, temp_dir=temp_dir)

        temp_sql = temp_dir / "AllPrintings_postgres.psql"
        _preprocess_for_postgres(psql_path, out_path=temp_sql)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_copy = debug_dir / f"AllPrintings_postgres_{timestamp}.psql"
        shutil.copyfile(temp_sql, debug_copy)
        print(f"Saved preprocessed SQL for analysis to: {debug_copy}")

        env["PGCLIENTENCODING"] = "UTF8"
        print(f"Loading into Postgres ({env['PGHOST']}:{env['PGPORT']} / {env['PGDATABASE']})...")
        c.run(
            f'psql -h "{env["PGHOST"]}" -p "{env["PGPORT"]}" -U "{env["PGUSER"]}" '
            f'-d "{env["PGDATABASE"]}" -f "{temp_sql}" -v ON_ERROR_STOP=1',
            env=env,
        )
        print("Initial load complete.")


@task
def card_types(c: Context, batch_size: int = 500) -> None:
    """Backfill public.card_types from mtgjson.cards.types (comma-separated).

    - Pages cards missing any row in public.card_types (keyset by uuid).
    - Inserts only standard rulebook types (see _ALLOWED_CARD_TYPES in this module).
    - One multi-row INSERT per page (``ON CONFLICT DO NOTHING``).
    - Counts tokens outside that set as skipped (summary at end).
    """

    if batch_size < 1:
        raise Exit("batch_size must be >= 1")

    env = pg_env()
    asyncio.run(_backfill_card_types(env=env, batch_size=batch_size))
    print("Done: card_types backfill complete.")


@task
def card_subtypes(c: Context, batch_size: int = 500) -> None:
    """Backfill public.card_subtypes from mtgjson.cards.subtypes.

    - Pages cards missing any row in public.card_subtypes (keyset by uuid).
    - Inserts distinct subtype tokens per card.
    """
    if batch_size < 1:
        raise Exit("batch_size must be >= 1")

    env = pg_env()
    asyncio.run(_backfill_card_subtypes(env=env, batch_size=batch_size))
    print("Done: card_subtypes backfill complete.")


@task
def card_supertypes(c: Context, batch_size: int = 500) -> None:
    """Backfill public.card_supertypes from mtgjson.cards.supertypes.

    - Pages cards missing any row in public.card_supertypes (keyset by uuid).
    - Inserts only supported supertypes (Basic, Legendary, etc.).
    """
    if batch_size < 1:
        raise Exit("batch_size must be >= 1")

    env = pg_env()
    asyncio.run(_backfill_card_supertypes(env=env, batch_size=batch_size))
    print("Done: card_supertypes backfill complete.")


ns = Collection("populate")
ns.add_task(mtg_json, name="mtg_json")
ns.add_task(card_types, name="card_types")
ns.add_task(card_subtypes, name="card_subtypes")
ns.add_task(card_supertypes, name="card_supertypes")
