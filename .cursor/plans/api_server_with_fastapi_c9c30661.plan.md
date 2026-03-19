---
name: API server with FastAPI
overview: "Stand up a minimal FastAPI server in the **api/ subfolder** of the project (api/pyproject.toml, api/app/, api/README.md). Use uv, Ruff, mypy, and import-linter. First step: healthcheck only; later add Postgres and card endpoints. Keep the stack simple for a hobby project (Windows)."
todos: []
isProject: false
---

# API server with FastAPI

## Recommendation: FastAPI

**FastAPI** is a good fit and keeps things simple:

- **Quick to build:** Minimal boilerplate, automatic OpenAPI docs at `/docs`, type hints.
- **LLM tool use:** Easy to expose a small set of endpoints; OpenAPI schema can later drive tool definitions for LM Studio.
- **Python:** Fits data/query work and any future LLM-side scripts in the same repo.
- **Hobby-friendly:** No auth or heavy framework; add only what you need.

**Alternative:** If you prefer TypeScript/Node, **Fastify** or **Express** plus **pg** would also be simple.

---

## Tooling (Python / Windows)

- **uv** — Python version and package management (replaces pip/venv for this project). Good Windows support; use `uv venv`, `uv add`, `uv sync`, `uv run`.
- **Ruff** — Linting and formatting. Run as `uv run ruff check .` and `uv run ruff format .`.
- **mypy** — Strict type checking. Run as `uv run mypy .`; enforce in CI or pre-commit.
- **import-linter** — Package/import cycle management. Configure in `pyproject.toml`; run with `uv run lint-imports` (or the command you define). Keeps `api/` dependency graph acyclic.

**Commands to whitelist (for Cursor/sandbox):** Allow **network** when running `uv add ...` and `uv sync` so dependencies can be installed. Ruff, mypy, and import-linter typically need no special permission.

---

## Scope (keep it simple)

- **All API code and config live in the `api/` subfolder:** `api/pyproject.toml`, `api/app/` (Python package), `api/README.md`. No API-related pyproject.toml at repo root; dependency and package layout are managed by **uv** inside `api/`.
- **No auth** for now (local/hobby).
- **Strict typing:** mypy in strict or near-strict mode; type hints on all public API and dependencies.
- **First step:** Only a **healthcheck** endpoint that does nothing (no DB, no card routes). Add Postgres and card search/get in a follow-up once healthcheck and tooling are in place.
- **Later:** Connect to Postgres via **POSTGRES_*** env; query `**mtgjson`** schema with raw SQL or a thin wrapper; add `GET /cards/search`, `GET /cards/{id}`, etc.
- **Run locally** from the `api/` directory: `uv run uvicorn app.main:app --reload`. Optional Docker later.

---

## Implementation plan

### Phase 1: Healthcheck only (this iteration)

**1. Python project with uv (inside `api/`)**

- **In the `api/` subfolder only:** create **api/pyproject.toml** with `[project]` (e.g. name `magic-boto-api`, dependencies: `fastapi`, `uvicorn[standard]`), and dev deps for **ruff**, **mypy**, **import-linter**. No pyproject.toml at repo root for the API. From `api/`: `uv sync`. No `requirements.txt`; uv + api/pyproject.toml are the source of truth.

**2. Linting and type enforcement**

- **Ruff:** `[tool.ruff]` and `[tool.ruff.format]` in **api/pyproject.toml**, with `src = ["app"]`. Run from `api/`: `uv run ruff check .`, `uv run ruff format .`
- **mypy:** `[tool.mypy]` in **api/pyproject.toml** with strict options and `packages = ["app"]`. Run from `api/`: `uv run mypy app`. All app code typed.
- **import-linter:** `[tool.importlinter]` in **api/pyproject.toml** (e.g. acyclic_siblings for package `app`). Run from `api/`: `uv run lint-imports`. Document in api/README.

**3. API layout and healthcheck**

- **api/app/** — Python package (`api/app/__init__.py`, `api/app/main.py`).
- **api/app/main.py** — FastAPI app; single endpoint **GET /health** returning 200 and e.g. `{"status": "ok"}`. No database, no other routes. Fully typed for mypy.
- **api/README.md** — How to run from `api/`: `uv sync`, then `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`. How to run Ruff, mypy, import-linter. Note API is the future tool backend for the LLM; Postgres and card endpoints come later.

**4. Commands to whitelist**

- Allow **network** when running `uv add ...` and `uv sync`. Ruff, mypy, import-linter need no special permission.

### Phase 2 (later): Postgres and card endpoints

- Add **POSTGRES_***-based DB connection (e.g. in `api/app/dependencies.py`); optional healthcheck DB ping.
- Connect to Postgres using **POSTGRES_*** from the environment.
- Query `**mtgjson`** schema (e.g. `SELECT ... FROM mtgjson.cards WHERE ...`). Table names depend on the mtgjson dump; you can inspect `tools_api/debug/schema.sql` if you’ve dumped it, or probe with a simple endpoint that lists tables in `mtgjson`.
- No migrations in the API repo for now; the catalog is read-only and lives in `mtgjson`; app-specific tables (inventory) come later.

### 3. Starter endpoints

- **Health:** `GET /health` — return 200 and optionally `{"db": "ok"}` if a simple `SELECT 1` works.
- **Search:** `GET /cards/search?q=...` — parameterized query against the mtgjson table(s) that store card name/text; return JSON list of matching cards (or ids + names first).
- **Get by id/uuid:** `GET /cards/{id}` or by uuid — return one card’s details from `mtgjson`.

Exact SQL and response shapes depend on the mtgjson schema (table and column names). You can start with a minimal search that uses a known table (e.g. from schema dump) and expand once you confirm the structure.

### 4. Running the API

- **Local:** From the **api/** directory, load env if needed (e.g. via `.\scripts\load-env.ps1` at repo root or set env vars another way), then `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`. Document in **api/README.md**.
- **Optional:** Add an **api** service to [docker-compose.yml](docker-compose.yml) that builds from `api/` and depends on `postgres` with `POSTGRES`_* set from env_file, so `docker compose up` brings up DB + API. Can be a follow-up to keep the first iteration “run on host with uvicorn.”

### 5. Docs and project plan

- **api/README.md** (in the API subfolder): how to install deps (e.g. `uv sync from api/`), set env (or use repo's load-db-env for Phase 2), run uvicorn from `api/` with `app.main:app`, and that the API is the “tool” backend for the LLM.
- Update [docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md) monorepo table to state that `api/` is the FastAPI server (optional one-line change).

---

## Summary


| Item         | Choice                                              |
| ------------ | --------------------------------------------------- |
| Package mgmt | uv + pyproject.toml (no requirements.txt)           |
| Linting      | Ruff (check + format)                               |
| Types        | mypy strict (or near-strict)                        |
| Cycles       | import-linter in pyproject.toml                     |
| Phase 1      | Healthcheck only: GET /health, no DB                |
| Phase 2      | Postgres + mtgjson + card search/get                |
| Run          | From `api/`: `uv run uvicorn app.main:app --reload` |
| Whitelist    | Network for `uv add` / `uv sync`                    |


(Phase 1 is minimal; Phase 2 adds DB and card routes.) one app file or app + one router, one DB dependency, and 2–3 endpoints. Add more routes and Docker once this runs and you’ve confirmed the mtgjson table layout.