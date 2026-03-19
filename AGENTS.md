# Agent instructions

Guidance for AI agents (e.g. Cursor) working in this repo.

## General

- **Prefer libraries over custom code.** Before adding types, helpers, or integrations, check whether an official or widely adopted library already provides them. Use those so the codebase stays aligned with specs and benefits from upstream fixes.

## Architecture / Guidelines

Apply these principles so new work fits the existing structure.

- **Service boundaries.** The repo is multi-service (e.g. agent_api, tools_api). Each service is self-contained (own app, settings, tasks, pyproject, Dockerfile). Run tooling (Ruff, mypy, Invoke) from the service directory you are changing.

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

## Python (tools_api/ and agent_api/)

- **Sibling imports.** Within the same package (e.g. modules under `app/models/`), prefer relative imports (`from .base import Base`, `from .sibling import Foo`) instead of fully qualified `app....` paths. Use absolute `app....` imports when crossing package boundaries (e.g. `app/services` → `app/schema`).

- **Immutability and read-only contracts.** Prefer immutable/read-only types in signatures and returns: `Mapping` instead of `dict`, `Sequence` instead of `list` where mutation is not needed.

- **Type stubs for dependencies.** When a dependency lacks types, add a stub package if one exists so the codebase stays strictly typed.

- **Lint and format from the service directory.** After any Python change under that service, run from its directory: `uv run ruff check .` (use `--fix` when appropriate), then `uv run ruff format .`. Fix any reported issues.

- **Type-check from the service directory.** Run `uv run mypy app tasks` (and `migrations` if present). In lint/CI, use `--no-incremental --cache-dir=nul` (Windows) or `--cache-dir=/dev/null` (Unix) to avoid stale cache.

- **Env is populated before run.** The app does not load `.env`. Populate the environment first (e.g. script or Docker); then start the server or run tasks.

- **Use the service’s own tasks.** Invoke tasks (serve, lint, migrate, etc.) are defined per service; run them from that service’s directory.

- **Confirm before running migrations.** Create or edit migration files as requested; do not run migrations unless the user confirms.

- **Prefer SQL portability.** When adding schema/migrations, prefer broadly compatible SQL constructs. Avoid PostgreSQL-specific features like native `ENUM` types when a portable alternative exists. For “enum-like” columns, use a `TEXT` column plus a CHECK constraint via `tools_api/migrations/check_constraints.py` (`create_allowed_values_check_constraint` / `drop_allowed_values_check_constraint`).

- **Seed MTGJSON before tools_api migrations.** Before applying Alembic migrations in `tools_api/migrations/`, run the MTGJSON load task from `tools_api/`: `uv run invoke populate.mtg_json`, since the migrations expect `mtgjson` tables to already exist.

- **Apply tools_api migrations from the tools README.** For migration commands/flow, follow `tools_api/migrations/README.md` (DRY: this is where “Apply all” is documented).

- **Consult `tools_api/debug/schema.sql` for DB questions.** Especially for tables/views that are not fully generated from migrations (e.g. MTGJSON), check `tools_api/debug/schema.sql` to confirm types/constraints.

- **Never hand-edit `tools_api/debug/schema.sql`.** When you need it synced after DB/migration changes, regenerate it via `uv run invoke populate.schema` from `tools_api/`. This uses `pg_dump -s` to dump the current DB schema into `tools_api/debug/schema.sql`.

- **DB access via app injection.** Routes that need the DB use the app’s dependency (session or connection); do not repeat the dependency in each route.

## Platform

- **Windows / PowerShell.** Scripts and docs use PowerShell; avoid bash or Unix-only commands.
