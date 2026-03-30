# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Architecture, conventions, and guidelines live in [AGENTS.md](AGENTS.md) — read it before making changes.

## Environment

Copy `.env.example` to `.env` at the project root and fill in values. Load it into your shell once before running any invoke tasks:

```powershell
. .\load-env.ps1   # dot-source from the project root
```

The dot (`. `) is required — it loads vars into your current shell. Running `.\load-env.ps1` directly won't work (vars are lost when the subprocess exits).

`ANTHROPIC_API_KEY` is only required for `generate.tags`. All other tasks only need the Postgres vars.

## Commands

All commands run from `tools_api/`.

### Serve

```powershell
uv run invoke serve.local    # Postgres in Docker + uvicorn locally
uv run invoke serve.docker   # full Docker stack
uv run invoke serve.mcp      # MCP streamable HTTP
```

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

### Tests

```powershell
uv run pytest
uv run pytest tests/path/to/test_file.py::test_name
```

### Other

```powershell
uv run invoke fetch                          # fetch & ingest MTGJSON catalog
uv run invoke generate.db-schema             # regenerate tools_api/debug/schema.sql
uv run invoke generate.tags --tag <name>     # run unattended Claude tag sweep (requires ANTHROPIC_API_KEY)
```

## Quick orientation

Two processes, one image (`tools_api/`): `app.http.main:app` (FastAPI, port 8000) and `app.mcp.asgi:app` (MCP streamable HTTP, port 8765). Shared domain code is in `app/services`, `app/schema`, `app/models`, `app/db`.

MCP tools are organized by resource under `app/mcp/tools/` — one `register_*_tools(app_mcp)` function per module, all wired in `app/mcp/tools/__init__.py`.

DB session lifecycle: services never commit; the tool or route that opens the session calls `session.commit()`.
