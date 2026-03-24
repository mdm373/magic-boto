# Migrations

## Prerequisite: seed the MTGJSON schema

The Alembic migrations in this folder apply changes to tables under the `mtgjson` schema.
Those tables are created by the initial MTGJSON load task under `tools_api`.

Run from the `tools_api/` directory with `POSTGRES_*` set in the environment (see repo `.env.example`).

- Seed MTGJSON (one-time): `uv run invoke populate.mtg_json`
- Apply all: `uv run alembic upgrade head`
- Roll back one: `uv run alembic downgrade -1`
- Current: `uv run alembic current`
