# Agent instructions

Guidance for AI agents (e.g. Cursor) working in this repo.

## General

- **Prefer standard existing libraries over custom code.** Before implementing types, helpers, or integrations (e.g. API response models, protocol handling), check whether an official or widely used library already provides them (e.g. `openai` for OpenAI API types, type stubs for dependencies). Use those instead of hand-rolling equivalents so the codebase stays aligned with specs and benefits from upstream fixes and updates.

## Python (api/)

- **Prefer immutability and functional style.** In API code (and elsewhere), prefer immutable/read-only types for signatures and return types: use `Mapping` (from `collections.abc`) instead of `dict` for map-like return types and input args, and `Sequence` instead of `list` where order matters but mutation is not needed. This keeps contracts clear and avoids accidental mutation.
- **Prefer type stubs for new deps.** When adding a new dependency that lacks inline types (e.g. triggers mypy “missing stubs” or “import-untyped”), add a corresponding stub package if one exists (e.g. `asyncpg-stubs`, `types-*`, or the library’s own stubs). This keeps the codebase strictly typed and avoids `# type: ignore` or broad `Any` types.
- **Always run Ruff when making code changes.** After any create or edit of Python under `api/` (including `api/app/`, `api/migrations/`, and `api/tasks/`), run from the `api/` directory—do not skip this:
  - `uv run ruff check .`
  - `uv run ruff format .`
- **Fix Ruff feedback.** If Ruff reports errors or suggests fixes, apply the fixes (or use `uv run ruff check . --fix` where appropriate) and re-run until both check and format pass.
- **Type-check.** From `api/`, run `uv run mypy app migrations tasks` and address any type errors.
- **Invoke tasks.** From `api/`, `uv run invoke serve.start` and `uv run invoke migrate` run the server and migrations; they load `.env` from the repo root automatically.
- **DB migrations:** Always check with the user before running a migration (`uv run invoke migrate` or `uv run alembic upgrade`). Create or edit migration files as requested, but do not run them unless the user confirms.
- **Routers that need DB:** Use `app.db`: for **ORM** routes add `dependencies=[Depends(inject_session_into_request)]` and use `session = get_request_session(request)`; for **raw SQL** add `dependencies=[Depends(inject_conn_into_request)]` and use `conn = get_request_conn(request)`. Do not repeat the dependency in each route.

## Platform

- **Windows / PowerShell.** Scripts and docs use PowerShell; avoid bash or Unix-only commands in this repo.
