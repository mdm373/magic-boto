# magic-boto-api

API server for magic-boto; the LLM uses it as a **tool** (card search, inventory, etc.). Phase 1: healthcheck only. Phase 2: Postgres + card endpoints.

## Setup

From this directory (`api/`):

```powershell
uv sync
```

## Run

From this directory, either use **Invoke** (loads `.env` from repo root automatically) or run uvicorn directly:

```powershell
uv run invoke server.start
```

Or: `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

Open http://localhost:8000/docs for OpenAPI, http://localhost:8000/health for the healthcheck.

## Invoke tasks

From `api/`, tasks load `.env` from the repo root so you don’t need to dot-source env first.

- **server.start** — run the API server (uvicorn).
- **db.migrate** — run Alembic migrations (`alembic upgrade head`).

List all: `uv run invoke --list`.

## Lint and types

From this directory:

- **Ruff:** `uv run ruff check .` and `uv run ruff format .`
- **mypy:** `uv run mypy app`
- **import-linter:** `uv run lint-imports` (config: `.importlinter` in this directory, layers contract)

## Migrations (Alembic)

From `api/`: `uv run invoke db.migrate` (loads env), or `uv run alembic upgrade head` with `POSTGRES_*` set. See `migrations/README.md`.

## Env

Use the same `POSTGRES_*` env as the rest of the repo (e.g. dot-source `..\db\scripts\load-db-env.ps1` from repo root).
