# tools_api app restructure

## Goal

Establish clear, consistent top-level package boundaries.

| Package | Responsibility |
|---|---|
| `app/cmd/` | Every runnable CLI/server entrypoint, one file per command |
| `app/services/` | All domain and application logic (DB, Anthropic, serialisation, validation). Barrel-exports top-level files from `__init__.py`; sub-packages are **not** re-exported through the barrel. |
| `app/services/mtgjson_fetch/` | MTGJSON fetch support code (sub-package of services, not barrelled) |
| `app/http_routing/` | FastAPI router definitions |
| `app/mcp_tooling/` | MCP tool definitions plus MCP server wiring and middleware |
| `app/prompts/` | Claude system/user prompt markdown files |
| `app/message_schema/` | JSON schemas for Claude structured output |
| `app/models/` | SQLAlchemy ORM models — unchanged |
| `app/api_schema/` | Pydantic request/response schemas (HTTP + MCP) — renamed from `app/schema/` |
| `app/db.py`, `app/log.py`, `app/errors.py` | Shared infrastructure — unchanged |

Packages being **deleted entirely**: `app/tag/`, `app/http/`, `app/mcp/`, `app/inventory/`, `app/validators/`, `app/fetch/`.

---

## File moves

### Commands → `app/cmd/`

Drop the `__init__.py + main.py` wrapper. Each command is a single `.py` file.
New `__init__.py` needed at: `app/cmd/`, `app/cmd/tag/`, `app/cmd/tag/sweep/`, `app/cmd/tag/audit/`, `app/cmd/inventory/`, `app/cmd/mcp/`.

| From | To |
|---|---|
| `app/tag/sweep/kickoff/main.py` | `app/cmd/tag/sweep/kickoff.py` |
| `app/tag/sweep/poll/main.py` | `app/cmd/tag/sweep/poll.py` |
| `app/tag/sweep/process/main.py` | `app/cmd/tag/sweep/process.py` |
| `app/tag/sweep/reset/main.py` | `app/cmd/tag/sweep/reset.py` |
| `app/tag/audit/kickoff/main.py` | `app/cmd/tag/audit/kickoff.py` |
| `app/tag/audit/poll/main.py` | `app/cmd/tag/audit/poll.py` |
| `app/tag/audit/process/main.py` | `app/cmd/tag/audit/process.py` |
| `app/tag/create/main.py` | `app/cmd/tag/create.py` |
| `app/tag/delete/main.py` | `app/cmd/tag/delete.py` |
| `app/tag/get/main.py` | `app/cmd/tag/get.py` |
| `app/tag/rename/main.py` | `app/cmd/tag/rename.py` |
| `app/inventory/delete/main.py` | `app/cmd/inventory/delete.py` |
| `app/inventory/export/main.py` | `app/cmd/inventory/export.py` |
| `app/inventory/import/main.py` | `app/cmd/inventory/import.py` |
| `app/fetch/main.py` | `app/cmd/fetch.py` |
| `app/http/main.py` | `app/cmd/http.py` |
| `app/mcp/main.py` (stdio) | `app/cmd/mcp/stdio.py` |
| `app/mcp/asgi.py` (ASGI) | `app/cmd/mcp/asgi.py` |

> **Note:** `uvicorn` invocation changes from `app.http.main:app` → `app.cmd.http:app`, and `app.mcp.asgi:app` → `app.cmd.mcp.asgi:app`. Update `docker-compose.yml` and any invoke tasks.

### Domain code → `app/services/`

Top-level service files are barrel-exported from `app/services/__init__.py`. The `mtgjson_fetch` sub-package is not re-exported through the barrel — cmd files that need it import directly from `app.services.mtgjson_fetch.*`.

| From | To |
|---|---|
| `app/tag/card_payload.py` | `app/services/card_payload.py` |
| `app/tag/batch/client.py` | `app/services/batch_client.py` |
| `app/tag/batch/verdict.py` | `app/services/batch_verdict.py` |
| `app/inventory/import/csv_parser.py` | `app/services/inventory_csv_parser.py` |
| `app/inventory/import/merger.py` | `app/services/inventory_merger.py` |
| `app/inventory/names.py` | `app/services/inventory_names.py` |
| `app/validators/edition_validator.py` | `app/services/edition_validator.py` |
| `app/fetch/mtgjson_fetch_job.py` | `app/services/mtgjson_fetch/fetch_job.py` |
| `app/fetch/mtgjson_file_client.py` | `app/services/mtgjson_fetch/file_client.py` |
| `app/fetch/mtgjson_model_mapper.py` | `app/services/mtgjson_fetch/model_mapper.py` |
| `app/fetch/mtgjson_schema.py` | `app/services/mtgjson_fetch/schema.py` |

### Routers → `app/http_routing/`

| From | To |
|---|---|
| `app/http/routers/card_router.py` | `app/http_routing/card_router.py` |
| `app/http/routers/edition_router.py` | `app/http_routing/edition_router.py` |
| `app/http/routers/tag_router.py` | `app/http_routing/tag_router.py` |

The FastAPI app factory in `app/cmd/http.py` imports from `app/http_routing/` to wire routers in.

### MCP tooling → `app/mcp_tooling/`

Includes tool definitions and the MCP server wiring/middleware that supports them.

| From | To |
|---|---|
| `app/mcp/tools/cards_tools.py` | `app/mcp_tooling/cards_tools.py` |
| `app/mcp/tools/editions_tools.py` | `app/mcp_tooling/editions_tools.py` |
| `app/mcp/tools/inventory_tools.py` | `app/mcp_tooling/inventory_tools.py` |
| `app/mcp/tools/tags_tools.py` | `app/mcp_tooling/tags_tools.py` |
| `app/mcp/server.py` | `app/mcp_tooling/server.py` |
| `app/mcp/error_middleware.py` | `app/mcp_tooling/error_middleware.py` |

### Prompts → `app/prompts/`

| From | To |
|---|---|
| `app/tag/batch/system_prompt.md` | `app/prompts/sweep/system_prompt.md` |
| `app/tag/audit/system_prompt.md` | `app/prompts/audit/system_prompt.md` |
| `app/tag/audit/user_prompt.md` | `app/prompts/audit/user_prompt.md` |

### Output schema → `app/message_schema/`

| From | To |
|---|---|
| `app/tag/batch/output_schema.json` | `app/message_schema/sweep_verdict.json` |

---

## Task invocation paths

Update all `-m` module paths in `tasks/sweep.py`, `tasks/audit.py`, and any inventory/fetch task files.

| Old | New |
|---|---|
| `app.tag.sweep.kickoff.main` | `app.cmd.tag.sweep.kickoff` |
| `app.tag.sweep.poll.main` | `app.cmd.tag.sweep.poll` |
| `app.tag.sweep.process.main` | `app.cmd.tag.sweep.process` |
| `app.tag.sweep.reset.main` | `app.cmd.tag.sweep.reset` |
| `app.tag.audit.kickoff.main` | `app.cmd.tag.audit.kickoff` |
| `app.tag.audit.poll.main` | `app.cmd.tag.audit.poll` |
| `app.tag.audit.process.main` | `app.cmd.tag.audit.process` |
| `app.tag.create.main` | `app.cmd.tag.create` |
| `app.tag.delete.main` | `app.cmd.tag.delete` |
| `app.tag.get.main` | `app.cmd.tag.get` |
| `app.tag.rename.main` | `app.cmd.tag.rename` |
| `app.inventory.delete.main` | `app.cmd.inventory.delete` |
| `app.inventory.export.main` | `app.cmd.inventory.export` |
| `app.inventory.import.main` | `app.cmd.inventory.import` |
| `app.fetch.main` | `app.cmd.fetch` |

---


---

### Schema rename

`app/schema/` → `app/api_schema/` (directory rename; all internal imports update from `app.schema` → `app.api_schema`).

## Cleanup

After all moves and import updates:

1. Delete `app/tag/`, `app/http/`, `app/mcp/`, `app/inventory/`, `app/validators/`
2. `uv run ruff check . --fix && uv run ruff format .`
3. `uv run mypy app tasks --no-incremental --cache-dir=nul`
