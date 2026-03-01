# db — Card catalog and app schema

Card data comes from [MTGJSON](https://mtgjson.com/). We use an **incremental** design long-term (SetList + per-set JSON + upsert); for now only the **initial load** is implemented. Updates will be incremental later (Phase 2, not yet implemented).

## Prerequisites

- Postgres running (e.g. `docker compose up -d` from repo root).
- [PostgreSQL client](https://www.postgresql.org/download/) installed so `psql` is on your PATH (for the initial-load script).
- Copy `.env.example` to `.env` in the repo root and set `POSTGRES_*` (and optionally `PG*`) if needed.

**Using psql without connection args:** `.env.example` includes the standard `PG*` vars that `psql` and `pg_dump` use. After copying to `.env`, load them into your shell once per terminal: from repo root run **`. .\db\scripts\load-db-env.ps1`** (dot-source). Then `psql`, `pg_dump`, etc. work with no `-h`/`-U`/`-d` flags.

## Initial load (one-time)

Load the full MTGJSON card catalog into Postgres once:

1. From repo root: `docker compose up -d`
2. Download **AllPrintings.psql** (or **AllPrintings.psql.zip** / **AllPrintings.psql.gz**) from [MTGJSON](https://mtgjson.com/downloads/all-files/) to your machine.
3. From this directory (`db/`), run the initial-load script: `.\scripts\load-mtgjson.ps1`  
   When prompted, enter the full path to your file (e.g. `C:\Users\You\Downloads\AllPrintings.psql.zip`).

The script extracts/decompresses if needed, then preprocesses the dump and runs it against the database. **All MTGJSON tables are created in the `mtgjson` schema** so the catalog is separate from your own tables (e.g. in `public`). Id columns are upgraded to BIGINT to avoid overflow. Connection settings are read from `.env` (or environment) in the repo root. The dump creates the card catalog tables (mtgsqlive schema).

**Check DB state:** Run `.\scripts\check-db.ps1` from `db/` to list tables and approximate row counts (useful to confirm the load or debug an empty DB).

**Querying the catalog:** MTGJSON tables live in the `mtgjson` schema. Use `mtgjson.tablename` in SQL (e.g. `SELECT * FROM mtgjson.cards`) or run `SET search_path TO mtgjson, public;` so unqualified names resolve there first.

## Migrations (app schema)

App-specific tables (e.g. **inventory**) will be added later, likely via an ORM in the API. See `db/migrations/README.md`.

## Updates (Phase 2, later)

When we implement incremental updates, a separate script will fetch SetList.json, determine new or changed sets, fetch only those set JSON files, and upsert into the catalog. Until then, there is no update path — the initial load is one-time only.
