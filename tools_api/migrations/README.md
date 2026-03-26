# Migrations

## What these migrations do

Alembic revisions under `tools_api/migrations/versions/` manage the **`magic_boto`** schema (editions, cards, junction tables, inventory, and related CHECK constraints).

They do **not** require the legacy `mtgjson` app tables. Load catalog data with the **fetch/ingest** pipeline (`app.fetch`) after the schema exists.

## Commands

Run from the `tools_api/` directory with `POSTGRES_*` set in the environment (see repo `.env.example`).

- Apply all: `uv run alembic upgrade head`
- Roll back one: `uv run alembic downgrade -1`
- Current: `uv run alembic current`

Or use the Invoke wrapper from `tools_api/`: `uv run invoke migrate` (same as `alembic upgrade head`).
