# Agent instructions

Guidance for AI agents (Claude Code, Cursor, etc.) working in this repo.

> **Never edit `CLAUDE.md`** — it imports this file. All changes go here in `AGENTS.md`.

## Environment

Copy `.env.example` to `.env` at the project root and fill in values. Load it into your shell once before running any invoke tasks:

```powershell
. .\load-env.ps1   # dot-source from the project root
```

The dot (`. `) is required — it loads vars into your current shell. `ANTHROPIC_API_KEY` is only required for tag **sweep** and **audit** flows (`sweep.*`, `audit.*`, and related MCP tools). All other tasks only need the Postgres vars.

## Commands

All commands run from `tools_api/`.

### Serve

```powershell
uv run invoke serve.local    # Postgres in Docker + uvicorn locally
uv run invoke serve.docker   # full Docker stack
uv run invoke serve.mcp      # MCP streamable HTTP
```

Root `docker-compose.yml` also includes **Redis**, **`tools_celery_worker`**, and **Flower** (Celery UI, default host port 5555). Set **`CELERY_REDIS_URL`** (defaults to `redis://localhost:6379/0`; Compose sets `redis://redis:6379/0`) in `.env`. Use **`--audit-after`** on sweep enqueue to chain audit after sweep.

### Lint & type-check

```powershell
uv run ruff check .
uv run ruff format .
uv run mypy app tasks --no-incremental --cache-dir=nul
```

### Migrations

```powershell
uv run invoke migrate          # upgrade head
uv run invoke migrate.down     # downgrade -1
uv run invoke migrate.create   # prompts for message, creates revision file
```

Migration files: `tools_api/migrations/versions/YYYYMMDD_revid_slug.py`. Create files when asked; **do not run migrations without user confirmation**.

### Other

```powershell
uv run invoke fetch                    # sync fetch & ingest MTGJSON catalog
uv run invoke sweep.enqueue --tag <name>
uv run invoke audit.enqueue --tag <name>
uv run invoke batch.poll               # Celery batch polling (prompts for batch IDs)
```

For a fuller command list, see the root **[README.md](README.md)**.

## Quick orientation

Two processes, one image (`tools_api/`): **`app.cmd.serve_http:app`** (FastAPI, port 8000) and **`app.cmd.serve_mcp.asgi:app`** (MCP streamable HTTP, port 8765) — see root **`docker-compose.yml`**. Shared domain code: **`app/services`**, **`app/api_schema`**, **`app/models`**, **`app/db`**.

MCP tools live under **`app/mcp_tooling/`**: one `register_*_tools(app_mcp)` per module, aggregated in **`app/mcp_tooling/tools.py`** into **`app/mcp_tooling/server.py`** (FastMCP factory).

**DB session lifecycle:** services never commit; the tool or route that opens the session commits. Open one session per logical unit of work — not one per service call. Only open separate sessions when each block needs its own independent commit boundary.

## Architecture / Guidelines

- **Prefer libraries over custom code.** Check for an official or widely adopted library before adding types, helpers, or integrations.

- **Service boundaries.** Runtime stack is **Postgres** + **tools_api** (FastAPI HTTP + MCP in one image). The **tools_api** service is self-contained (app, settings, tasks, pyproject, Dockerfile). Run tooling (Ruff, mypy, Invoke) from **`tools_api/`**.

- **Build at startup, inject into handlers.** App-wide resources are built once in lifespan and passed into handlers via closure or factory. Do not store them in untyped app state or re-fetch per request.

- **Constructor injection for stateful behavior.** Stateful or multi-step behavior lives in a class that receives dependencies in `__init__`. Use an async factory to build and wire dependencies.

- **Prefer factory functions for DI.** Build routers/helpers via `create_*_router(...)` / factory functions with closure-based injection. Use `Depends(...)` only when the dependency must be request-scoped.

- **Encapsulate DI wiring in factory/entry modules.** Expose `create_*` factories from package `__init__.py` (e.g. `services.create_*`, `routers.create_*`). Keep route bodies thin.

- **Use package barrels for public APIs.** Re-export commonly used classes in `__init__.py` with `__all__` so consumers import from the package root.

- **Thin integration facades.** Expose one small entry point per external capability; keep implementation in separate single-concern modules. Reuse shared resources (HTTP clients, caches).

- **Raise, don't return errors.** Use one exception type and one app-level handler. Routes raise; they do not build error responses by hand.

- **Type boundaries explicitly.** Use library/SDK types at API boundaries. Validate request bodies (e.g. Pydantic `TypeAdapter`); avoid untyped `dict` at edges. Expose `Mapping` and `Sequence` (read-only) instead of `dict` and `list`. Prefer a functional style—no side effects, data in and data out.

- **One concern per module.** Each file has one clear responsibility. Split large routers or monolithic logic by concern.

- **No vague "helpers" dumping grounds.** Do not add generic top-level modules (e.g. `helpers.py`, `utils.py`). Put small utilities in the package that owns their use.

## Python (tools_api/)

- **Sibling imports.** Within a package, prefer relative imports (`from .base import Base`). Use absolute `app....` imports when crossing package boundaries. Do not import through the `app.models` barrel from inside `app.models` — that re-enters `__init__` and causes cycles.

- **SQLAlchemy 2 bidirectional relationships and import cycles.** Parent/child ORM modules must not both import each other at **runtime**. Use this pattern:
  - **Prefer one-way runtime import when safe:** if module **A** only needs **B**'s type under `TYPE_CHECKING`, then **B** may use a runtime import of **A** with an unquoted `Mapped[AModel]`. If **A** ever gains a runtime import of **B**, revert **B** to `TYPE_CHECKING` + string forward refs.
  - **When cycles are unavoidable:** add `TYPE_CHECKING` imports for mypy only. On `relationship` fields use string forward refs inside `Mapped[...]` (e.g. `Mapped["list[ChildModel]"]`). Use `list[...]` for one-to-many collections; SQLAlchemy requires a concrete collection type.
  - **Ruff** is configured (`per-file-ignores` in `pyproject.toml` for `app/models/**/*.py`, **UP037** / **F821**) to allow quoted `Mapped` forward refs. Do not remove those ignores.

- **Immutability.** Prefer `Mapping` over `dict`, `Sequence` over `list` in signatures and returns. For small fixed sets of related values, use `@dataclass(frozen=True, slots=True)` with immutable container types on fields.

- **Type stubs.** When a dependency lacks types, add a stub package if one exists.

- **Logging.** Use **loguru** (`from loguru import logger`) in all `app/` code — not `print()`. Configure stderr once at the CLI entrypoint. `tools_api/tasks/` may use `print()` / `input()` for Invoke-driven operator prompts only.

- **Lint and format after every Python change.** From `tools_api/`: `uv run ruff check . --fix`, then `uv run ruff format .`.

- **Type-check from the service directory.** `uv run mypy app tasks --no-incremental --cache-dir=nul`.

- **Env is pre-populated.** The app does not load `.env`. Populate the environment before starting the server or running tasks.

- **Invoke task modules (`tools_api/tasks/`) must never import from `app`.** Task files wire Invoke only (`@task`, `Collection`, `Context.run`). If a task needs app logic, put it in a `python -m app....` CLI and invoke via `c.run(...)`.

- **Invoke tasks prompt; `python -m app....` mains take argv only.** Interactive flows belong in `tasks/`. Entrypoints under `app/` are non-interactive: parse `sys.argv`, validate, run.

- **Invoke task naming.** `uv run invoke <namespace>.<task>`. Name functions `verb_noun` in snake_case (Invoke shows hyphens in `--list`). Examples: `serve.local`, `migrate`, `fetch`, `sweep.enqueue`, `audit.enqueue`.

- **Prefer SQL portability.** Avoid PostgreSQL-specific features like native `ENUM` types. Use `TEXT` + CHECK constraint via `tools_api/migrations/check_constraints.py`.

- **Migrations.** Create/edit files under `tools_api/migrations/versions/`; apply with `uv run invoke migrate`. See `tools_api/migrations/README.md`. **Do not run migrations unless the user confirms.**

- **Catalog data** lives in the **`magic_boto`** schema. Load MTGJSON via `uv run invoke fetch` or the async job pipeline (see `docs/PROJECT-PLAN.md`).

- **`tools_api/debug/schema.sql`** is the authoritative DB schema reference. Never hand-edit it — regenerate via `uv run invoke generate.db-schema`.

- **DB access via app injection.** Routes use the app's session dependency; do not repeat it per route.

- **HTTP vs MCP entrypoints.** FastAPI: `uvicorn app.cmd.serve_http:app`. MCP streamable HTTP: `uvicorn app.cmd.serve_mcp.asgi:app`. MCP stdio: `uv run python -m app.cmd.serve_mcp.stdio`. FastMCP wiring: `app/mcp_tooling/server.py`.

- **Celery.** App in `app/cmd/serve_celery.py`. Task definitions in `app/worker/tasks.py`. Enqueue via the `app.worker` package barrel. Registered task names are `PipelineTaskName` enum values — do not import task callables from `tasks.py` outside that module.

- **MCP Inspector (Docker).** Connect with Streamable HTTP URL **`http://tools_mcp:8765/mcp`** (Compose service name, not `localhost`). Check `docker compose logs mcp_inspector` for the proxy auth token if prompted.

- **LLM / orchestration.** No in-repo agent or chat UI. Use an external MCP-capable client pointed at `http://<host>:<port>/mcp`. System prompts and task instructions go under `tasks/` (e.g. `tasks/deck-building-instructions.md`). For deck building and inventory/deck edits, follow that file — MCP-only; do not run ad-hoc Python or SQL.

## TypeScript (`tools-ui/`)

- **Prefer `type` over `interface`** for object shapes and unions.
- **Read-only shapes** at type boundaries: `type Foo = Readonly<{ a: string; b: number }>` and `readonly T[]` for lists.
- **String unions:** define a const tuple and derive the union — `const FooValues = ["a", "b"] as const`, `type FooValue = (typeof FooValues)[number]`.
- **Keyed lookup tables:** use `ReadonlyRecord<K, V>` from `tools-ui/src/types/utils.ts` instead of bare `Record<K, V>`.

## Platform

- **Windows / PowerShell.** Scripts and docs use PowerShell; avoid bash or Unix-only commands.
