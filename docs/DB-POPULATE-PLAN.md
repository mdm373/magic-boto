# Card catalog in Postgres

The app uses the **`magic_boto`** schema (Alembic under `tools_api/migrations/`). Catalog rows are **not** loaded with the legacy `psql` AllPrintings dump.

## Current flow

1. **Schema:** From `tools_api/`, apply migrations (`uv run invoke migrate` or `uv run alembic upgrade head`).
2. **Data:** Run the MTGJSON fetch/ingest pipeline (`app.fetch`), which upserts into `magic_boto` (e.g. `uv run invoke fetch` from `tools_api/`).

See [PROJECT-PLAN.md](PROJECT-PLAN.md) for overall architecture.
