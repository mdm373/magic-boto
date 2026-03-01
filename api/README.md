# magic-boto-api

Single API server for magic-boto: **agent** (OpenAI-compatible chat under `/openapi/v1/`) + **tools** (card search, deck validation, rules). The agent runs the tool loop in-process; tool HTTP routes exist for contract and debugging. See [docs/PROJECT-PLAN.md](../docs/PROJECT-PLAN.md).

## Setup

From this directory (`api/`):

```powershell
uv sync
```

## Run

From this directory, either use **Invoke** (loads `.env` from repo root automatically) or run uvicorn directly:

```powershell
uv run invoke serve.start
```

Or: `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

Open http://localhost:8000/docs for OpenAPI, http://localhost:8000/health for the healthcheck.

## Development with Docker

From the **repo root**, `docker compose up` runs the stack. The API service mounts `api/app` and runs uvicorn with `--reload`, so edits under `app/` take effect without rebuilding.

## Invoke tasks

From `api/`, tasks load `.env` from the repo root so you don’t need to dot-source env first.

- **serve.start** — run the API server (uvicorn).
- **migrate** — run Alembic migrations (`alembic upgrade head`).

List all: `uv run invoke --list`.

## Lint and types

From this directory:

- **Ruff:** `uv run ruff check .` and `uv run ruff format .`
- **mypy:** `uv run mypy app`
- **import-linter:** `uv run lint-imports` (config: `.importlinter` in this directory, layers contract)

## Migrations (Alembic)

From `api/`: `uv run invoke migrate` (loads env), or `uv run alembic upgrade head` with `POSTGRES_*` set. See `migrations/README.md`.

## Env

Use the same `POSTGRES_*` env as the rest of the repo (e.g. dot-source `..\db\scripts\load-db-env.ps1` from repo root).
