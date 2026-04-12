# Agent instructions

Guidance for AI agents (Claude Code, Cursor, etc.) working in this repo.

## This file

`CLAUDE.md` is a symbolic link to this file — **never edit `CLAUDE.md` directly**. All changes go here in `AGENTS.md`. To (re)create the symlink on Windows:

```powershell
New-Item -ItemType SymbolicLink -Path CLAUDE.md -Target AGENTS.md -Force
```

Requires PowerShell as Administrator or Windows 11 Developer Mode enabled.

## Environment

Copy `.env.example` to `.env` at the project root and fill in values. Load it into your shell once before running any invoke tasks:

```powershell
. .\load-env.ps1   # dot-source from the project root
```

The dot (`. `) is required — it loads vars into your current shell. Running `.\load-env.ps1` directly won't work (vars are lost when the subprocess exits).

`ANTHROPIC_API_KEY` is only required for `generate.tags` and `generate.audit-tags`. All other tasks only need the Postgres vars.

## Commands

All commands run from `tools_api/`.

### Serve

```powershell
uv run invoke serve.local    # Postgres in Docker + uvicorn locally
uv run invoke serve.docker   # full Docker stack
uv run invoke serve.mcp      # MCP streamable HTTP
```

Root `docker-compose.yml` also includes **Redis**, **`tools_celery_worker`**, and **Flower** (Celery UI, default host port 5555). Set **`CELERY_REDIS_URL`** (defaults to `redis://localhost:6379/0`; Compose sets `redis://redis:6379/0`) in `.env` for Celery. After tag sweep or audit enqueue submits batches, the CLI enqueues Celery to poll and process; use **`--audit-after`** on sweep enqueue to chain audit after sweep.

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
uv run invoke fetch                               # fetch & ingest MTGJSON catalog
uv run invoke generate.tags --tag <name>          # run unattended Claude tag sweep (requires ANTHROPIC_API_KEY)
uv run invoke generate.audit-tags --tag <name>    # audit sweep results with Claude Opus (requires ANTHROPIC_API_KEY)
```

## Quick orientation

Two processes, one image (`tools_api/`): `app.http.main:app` (FastAPI, port 8000) and `app.mcp.asgi:app` (MCP streamable HTTP, port 8765). Shared domain code is in `app/services`, `app/schema`, `app/models`, `app/db`.

MCP tools are organized by resource under `app/mcp/tools/` — one `register_*_tools(app_mcp)` function per module, all wired in `app/mcp/tools/__init__.py`.

DB session lifecycle: services never commit; the tool or route that opens the session calls `session.commit()`.

**Session scope:** open one session per logical unit of work — not one per service call. A sequence of reads, or a read-then-write that commits once, should share a single `async with session_factory() as session:` block. Only open separate sessions when each block genuinely needs its own independent commit boundary (e.g. a loop that records batches one at a time so a mid-loop failure does not roll back prior commits).

## General

- **Prefer libraries over custom code.** Before adding types, helpers, or integrations, check whether an official or widely adopted library already provides them. Use those so the codebase stays aligned with specs and benefits from upstream fixes.

## Architecture / Guidelines

Apply these principles so new work fits the existing structure.

- **Service boundaries.** Runtime stack is **Postgres** + **tools_api** (FastAPI HTTP + MCP in one image). The **tools_api** service is self-contained (app, settings, tasks, pyproject, Dockerfile). Run tooling (Ruff, mypy, Invoke) from **`tools_api/`** for Python changes there.

- **Build at startup, inject into handlers.** App-wide resources are built once in lifespan and passed into the code that needs them (e.g. a router factory that closes over them). Do not store them in untyped app state or re-fetch per request. The server is not ready until startup has finished.

- **Constructor injection for stateful behavior.** Stateful or multi-step behavior lives in a class that receives its dependencies in `__init__` and exposes a narrow entry point. Use an async factory to build and wire dependencies. Keep the core logic in one small module; extract helpers (context, message conversion, etc.) into separate modules.

- **Prefer factory functions for DI.** In most cases, build routers/helpers via `create_*_router(...)` / factory functions and closure-based injection so dependencies are explicit and testable. Use `Depends(...)` only when the dependency must be request-scoped or is only available at request time (avoid module-level singletons and `@staticmethod` helpers when not needed).

- **Encapsulate DI wiring in factory/entry modules.** Prefer `create_*` factories exposed from package `__init__.py` (e.g. `services.create_*`, `routers.create_*`) to hide how mappers/services are constructed and injected. Keep route bodies thin; let initialization modules own the wiring.

- **Use package barrels for public APIs.** For packages like `validators/` and `schema/`, re-export commonly used classes in the package `__init__.py` using `__all__` so consumers can import from the package root.

- **Thin integration facades.** For any external or cross-cutting capability, expose one small entry point and keep the implementation in separate, single-concern modules. Reuse shared resources (HTTP clients, caches) instead of creating them per call.

- **Raise, don’t return errors.** Use one exception type and one app-level handler that turns it into a response. Routes raise; they do not build error responses by hand.

- **Type boundaries explicitly.** Use library/SDK types at API boundaries. Validate request bodies (e.g. Pydantic `TypeAdapter`); avoid untyped `dict` at edges. Prefer immutable data everywhere: expose `Mapping` and `Sequence` (read-only) instead of `dict` and `list` in signatures and returns. Prefer a functional style—no side effects, data in and data out—so interfaces are easy to reason about and test.
- **One concern per module.** Each file has one clear responsibility. Split large routers or monolithic logic by concern.

- **No vague “helpers” dumping grounds.** Do not add generic top-level modules (e.g. `helpers.py`, `utils.py`, `openapi_helpers.py`). Put small utilities in the package that owns their use (e.g. schema/OpenAPI description text in `app/schema/descriptions.py`).

## Python (tools_api/)

- **Sibling imports.** Within the same package (e.g. modules under `app/models/`), prefer relative imports (`from .base import Base`, `from .sibling import Foo`) instead of fully qualified `app....` paths. Use absolute `app....` imports when crossing package boundaries (e.g. `app/services` → `app/schema`). Do not import through the `app.models` package barrel from inside `app.models` (e.g. avoid `from app.models import FooModel` in a sibling module); that re-enters `__init__` and causes cycles. Import the defining module instead (`from .foo_model import FooModel`).

- **SQLAlchemy 2 bidirectional relationships and import cycles.** Parent/child ORM modules must not both import each other at **runtime**. Use this pattern going forward:
  - **Prefer one-way runtime import when safe:** if module **A** only needs type hints for module **B**’s mapped class under `if TYPE_CHECKING:` (no runtime `from .b import BModel` in **A**), then **B** may use a **runtime** sibling import `from .a import AModel` and an unquoted `Mapped[AModel]` on its `relationship`. That avoids `TYPE_CHECKING` on **B** and keeps mypy happy (e.g. junction tables and `mtgjson_identifiers` → `mtgjson_card`). If **A** ever gains a runtime import of **B**, revert **B** to `TYPE_CHECKING` + string forward refs (or restructure) so you do not create a cycle.
  - **“Many” side on the parent when cycles are unavoidable:** add `if TYPE_CHECKING:` imports of related mapped classes for **mypy** only. On `relationship` fields, keep **string forward references** inside `Mapped[...]` (e.g. `Mapped["list[ChildModel]"]`, `Mapped["ParentModel | None"]`) so **SQLAlchemy** can resolve targets at mapper configuration time without those names existing at runtime. Use **`list[...]`** for one-to-many collections (not `collections.abc.Sequence`); SQLAlchemy requires a concrete collection type.
  - **Ruff** is configured in `tools_api/pyproject.toml` (`per-file-ignores` under `app/models/**/*.py` for **UP037** / **F821**) so quoted `Mapped` forward refs are not stripped and forward-ref names are not flagged as undefined. Do not remove those ignores to “fix” model-only lint noise; fix cycles by adjusting imports and annotations instead.

- **Immutability and read-only contracts.** Prefer immutable/read-only types in signatures and returns: `Mapping` instead of `dict`, `Sequence` instead of `list` where mutation is not needed.

- **Structured immutable bundles.** When returning a small fixed set of related values (e.g. several parallel collections from one parse step), prefer a **`@dataclass(frozen=True, slots=True)`** over hand-rolled classes with `__slots__` and a manual `__init__`. Prefer **immutable container types** on those fields (`tuple`, or a read-only `Sequence` contract) so the bundle stays immutable in practice; a `frozen` dataclass with mutable `list` fields still allows mutating list contents.

- **Type stubs for dependencies.** When a dependency lacks types, add a stub package if one exists so the codebase stays strictly typed.

- **Logging in `app/` (CLIs and runtime code).** Use **loguru** (`from loguru import logger`) for status, progress, and diagnostics—**do not use `print()`** for that purpose. Configure stderr once at the CLI entrypoint (`logger.remove()` / `logger.add(...)`, `LOG_LEVEL` from the environment; follow **`app/fetch/main.py`**). **`tools_api/tasks/`** may use **`print()`** / **`input()`** only for Invoke-driven prompts to the operator; code under **`app/`** should log through **loguru**.

- **Lint and format from the service directory.** After any Python change under that service, run from its directory: `uv run ruff check .` (use `--fix` when appropriate), then `uv run ruff format .`. Fix any reported issues.

- **Type-check from the service directory.** Run `uv run mypy app tasks` (and `migrations` if present). In lint/CI, use `--no-incremental --cache-dir=nul` (Windows) or `--cache-dir=/dev/null` (Unix) to avoid stale cache.

- **Env is populated before run.** The app does not load `.env`. Populate the environment first (e.g. script or Docker); then start the server or run tasks.

- **Use the service’s own tasks.** Invoke tasks (serve, lint, migrate, etc.) are defined per service; run them from that service’s directory.

- **Invoke task modules (`tools_api/tasks/`) must never import from `app`.** Task files are **only** for wiring Invoke (`@task`, `Collection`, `Context.run`). They must remain **self-contained to the `tasks` package**—no `from app...`, no `import app`, no reaching into `tools_api/app/` at import time. If a task needs application constants, services, or prompts, put that logic in a **`python -m app....`** CLI (or other entrypoint under `app/`) and **invoke it via `c.run(...)`** from the task. Breaking this rule couples the task loader to the app and breaks the intended split.

- **Invoke tasks prompt; `python -m app....` mains take argv only.** Interactive flows (asking the user for paths, names, confirmations) belong in **`tools_api/tasks/`** using **`input()`** / **`print()`** (or similar). Entrypoints under **`app/`** (e.g. `python -m app.inventory.import.main`) stay **non-interactive**: parse **`sys.argv`**, validate, then run. Do not add prompts or interactive branches to `main` modules; the task collects answers and confirmations and passes the final values as CLI arguments.

- **Invoke task naming.** From `tools_api/`, run `uv run invoke <namespace>.<task>`. Each path is **namespace** (group) **.** **task** (action). Name task functions **`verb_noun`** in snake_case—a **verb.noun** style (imperative verb + object); Invoke’s `-l` output uses hyphens for underscores (e.g. `all_sets` → `all-sets`). Some tasks use short verbs (`up`, `down`, `all`) where that matches siblings. Examples: `serve.local`, `import.inventory`, `migrate.up`, `fetch.all-sets`, `generate.db-schema`, `lint.all`. New tasks should follow this pattern.

- **Confirm before running migrations.** Create or edit migration files as requested; do not run migrations unless the user confirms.

- **Prefer SQL portability.** When adding schema/migrations, prefer broadly compatible SQL constructs. Avoid PostgreSQL-specific features like native `ENUM` types when a portable alternative exists. For “enum-like” columns, use a `TEXT` column plus a CHECK constraint via `tools_api/migrations/check_constraints.py` (`create_allowed_values_check_constraint` / `drop_allowed_values_check_constraint`).

- **Apply tools_api migrations from the tools README.** For migration commands/flow, follow `tools_api/migrations/README.md` (DRY: this is where “Apply all” is documented).

- **Catalog data** lives in the **`magic_boto`** schema. After migrations, load MTGJSON into it via `app.fetch` (e.g. `uv run invoke fetch` from `tools_api/`).

- **Consult `tools_api/debug/schema.sql` for DB questions.** Regenerate it from a live database when needed; it reflects whatever is installed (including **`magic_boto`** after migrations).

- **Never hand-edit `tools_api/debug/schema.sql`.** Regenerate it via `uv run invoke generate.db-schema` from `tools_api/` (`pg_dump -s` into `tools_api/debug/schema.sql`).

- **DB access via app injection.** Routes that need the DB use the app’s dependency (session or connection); do not repeat the dependency in each route.

- **tools_api HTTP vs MCP.** The FastAPI app is loaded via `uvicorn app.cmd.serve_http:app` (see `docker-compose.yml` **`tools_api`**). Streamable MCP HTTP matches that pattern: `uvicorn app.mcp.asgi:app` (see **`tools_mcp`**). Shared wiring for FastMCP lives in `app/mcp/server.py`. **Stdio** MCP hosts (subprocess-only clients): `uv run python -m app.mcp.main`. Shared domain code stays at `tools_api/app/` (`services`, `schema`, `db`, `models`).

- **Celery.** The app lives in `app/cmd/serve_celery.py` (`celery_app`, `create_celery_app`). Worker and Flower use `celery -A app.cmd.serve_celery:celery_app` (see **`tools_celery_worker`** / **`flower`**). Task definitions live in `app/worker/tasks.py`. Enqueue work from services/CLIs via `from app.worker import enqueue_materialize_sweep_batches, enqueue_process_sweep_polling, enqueue_process_audit_polling, enqueue_submit_batches, enqueue_init_tag_audit` (the package barrel is the public API). Registered task names are `PipelineTaskName` enum values in `app/worker/pipeline_task_names.py` and must match `name=` on the task decorators—do not import task callables from `tasks.py` outside that module (avoids cycles with code `tasks` already imports).

- **MCP Inspector (Docker).** Root **`docker-compose.yml`** includes **`mcp_inspector`** (`ghcr.io/modelcontextprotocol/inspector:latest`), ports **`MCP_INSPECTOR_CLIENT_PORT` / `MCP_INSPECTOR_SERVER_PORT`** (defaults **6274** / **6277**). Open the UI on the host, then connect with **Streamable HTTP** URL **`http://tools_mcp:8765/mcp`** (use the Compose service name so the proxy reaches `tools_mcp`; `http://localhost:8765/mcp` is wrong from inside the inspector container). Check **`docker compose logs mcp_inspector`** for the proxy auth token if prompted.

- **LLM / orchestration.** There is **no in-repo agent or chat UI**. Use an external MCP-capable client (Cursor, Claude Desktop, etc.) pointed at **`http://<host>:<port>/mcp`** (see **`TOOLS_MCP_PORT`**). Put **system prompts and task instructions in Markdown** under **`tasks/`** (or `docs/`) and reference them from your workflow or client rules (e.g. `tasks/deck-building/AGENTS.md`). For **deck building and inventory/deck edits**, follow **`tasks/deck-building/AGENTS.md`**: **MCP-only** for those flows—**do not** answer by running ad-hoc Python or SQL against Postgres instead of MCP tools.

## TypeScript (`tools-ui/`)

- **Prefer `type` over `interface`** for object shapes and unions (clearer equivalence with structural typing, no declaration merging surprises).
- **Read-only object shapes** at type boundaries: `type Foo = Readonly<{ a: string; b: number }>` (and `readonly T[]` for homogeneous lists). Runtime values may still come from `JSON.parse`; the types document intent and catch accidental mutation in code.
- **Finite string unions (“enums”):** define a const tuple and derive the union, e.g. `const FooValues = ["a", "b"] as const` and `type FooValue = (typeof FooValues)[number]`, then use `FooValue` in `Readonly<{ ... }>`. Keeps a single source of truth and a runtime array when you need iteration or guards.
- **Keyed lookup tables:** use `ReadonlyRecord<K, V>` from `tools-ui/src/types/utils.ts` instead of bare `Record<K, V>` when defining fixed key maps (same as `Readonly<Record<K, V>>`).

## Platform

- **Windows / PowerShell.** Scripts and docs use PowerShell; avoid bash or Unix-only commands.
