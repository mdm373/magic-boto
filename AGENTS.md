# Agent instructions

Guidance for AI agents (e.g. Cursor) working in this repo.

## General

- **Prefer libraries over custom code.** Before adding types, helpers, or integrations, check whether an official or widely adopted library already provides them. Use those so the codebase stays aligned with specs and benefits from upstream fixes.

## Architecture / Guidelines

Apply these principles so new work fits the existing structure.

- **Service boundaries.** The repo is multi-service (e.g. agent_api, tools_api). Each service is self-contained (own app, settings, tasks, pyproject, Dockerfile). Run tooling (Ruff, mypy, Invoke) from the service directory you are changing.

- **Build at startup, inject into handlers.** App-wide resources are built once in lifespan and passed into the code that needs them (e.g. a router factory that closes over them). Do not store them in untyped app state or re-fetch per request. The server is not ready until startup has finished.

- **Constructor injection for stateful behavior.** Stateful or multi-step behavior lives in a class that receives its dependencies in `__init__` and exposes a narrow entry point. Use an async factory to build and wire dependencies. Keep the core logic in one small module; extract helpers (context, message conversion, etc.) into separate modules.

- **Thin integration facades.** For any external or cross-cutting capability, expose one small entry point and keep the implementation in separate, single-concern modules. Reuse shared resources (HTTP clients, caches) instead of creating them per call.

- **Raise, don’t return errors.** Use one exception type and one app-level handler that turns it into a response. Routes raise; they do not build error responses by hand.

- **Type boundaries explicitly.** Use library/SDK types at API boundaries. Validate request bodies (e.g. Pydantic `TypeAdapter`); avoid untyped `dict` at edges. Prefer immutable data everywhere: expose `Mapping` and `Sequence` (read-only) instead of `dict` and `list` in signatures and returns. Prefer a functional style—no side effects, data in and data out—so interfaces are easy to reason about and test.

- **One concern per module.** Each file has one clear responsibility. Split large routers or monolithic logic by concern.

## Python (tools_api/ and agent_api/)

- **Immutability and read-only contracts.** Prefer immutable/read-only types in signatures and returns: `Mapping` instead of `dict`, `Sequence` instead of `list` where mutation is not needed.

- **Type stubs for dependencies.** When a dependency lacks types, add a stub package if one exists so the codebase stays strictly typed.

- **Lint and format from the service directory.** After any Python change under that service, run from its directory: `uv run ruff check .` (use `--fix` when appropriate), then `uv run ruff format .`. Fix any reported issues.

- **Type-check from the service directory.** Run `uv run mypy app tasks` (and `migrations` if present). In lint/CI, use `--no-incremental --cache-dir=nul` (Windows) or `--cache-dir=/dev/null` (Unix) to avoid stale cache.

- **Env is populated before run.** The app does not load `.env`. Populate the environment first (e.g. script or Docker); then start the server or run tasks.

- **Use the service’s own tasks.** Invoke tasks (serve, lint, migrate, etc.) are defined per service; run them from that service’s directory.

- **Confirm before running migrations.** Create or edit migration files as requested; do not run migrations unless the user confirms.

- **DB access via app injection.** Routes that need the DB use the app’s dependency (session or connection); do not repeat the dependency in each route.

## Platform

- **Windows / PowerShell.** Scripts and docs use PowerShell; avoid bash or Unix-only commands.
