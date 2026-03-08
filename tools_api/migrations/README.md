# Migrations

Run from the `tools_api/` directory. POSTGRES_* from env (e.g. load with `.\scripts\load-env.ps1` from repo root).

- Apply all: `uv run alembic upgrade head`
- Roll back one: `uv run alembic downgrade -1`
- Current: `uv run alembic current`
