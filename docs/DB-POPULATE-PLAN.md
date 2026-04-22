# Card catalog in Postgres

The app uses the **`magic_boto`** schema (Alembic under `tools_api/migrations/`). Catalog rows are **not** loaded with the legacy `psql` AllPrintings dump.

## Current flow

1. **Schema:** From `tools_api/`, apply migrations (`uv run invoke migrate` or `uv run alembic upgrade head`). See `tools_api/migrations/README.md`.
2. **Data:** Run the MTGJSON fetch/ingest pipeline — **`uv run invoke fetch`** from `tools_api/` (implementation under `app/cmd/fetch.py` and `app/services/mtgjson_fetch/`). Optional **async per-set jobs** (Postgres + Celery + MCP) are summarized in [PROJECT-PLAN.md](PROJECT-PLAN.md).

See [PROJECT-PLAN.md](PROJECT-PLAN.md) for overall architecture.
