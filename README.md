# magic-boto

> **MCP** for conversational **catalog** and **inventory** queries, **agent-assisted intent tagging**, and **MCP App UI** (carousels, card detail, job progress).

Connect an MCP-capable agent as in **Setup** below, then talk to it in natural language (catalog, inventory, tagging).

---

## What it does

- **Card Query:** search and page through the MTG catalog or your personal inventory with filters.
- **MTGJSON refresh:** update MCP's local catalog of card/edition data from mtgjson.com.
- **Inventory:** import card collection CSVs as inventories to search against.
- **Tags:** define and apply **intent** labels on cards (e.g. ramp, removal) using anthropic models.

The catalog comes from [MTGJSON](https://mtgjson.com). Tags are refined with agent help and stored with card data for search and deck workflows.

More detail: [docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md). Contributors: [AGENTS.md](AGENTS.md).

---

## Stack

- **Platform:** **Windows** is what we support today (PowerShell, paths, docs).
- **Python 3.11+:** FastAPI, SQLAlchemy 2, asyncpg, FastMCP, Alembic
- **MCP:** streamable HTTP tools (FastMCP) and **MCP App UI** (bundled interactive views: cards, MTGJSON jobs, inventory import, …)
- **Postgres 16:** `magic_boto` schema
- **Docker Compose:** Postgres, app services, Redis, Celery worker, MCP, optional Inspector
- **Celery + Redis:** background jobs (e.g. MTGJSON fetch pipelines, tag batch work)
- **Anthropic SDK:** batch-style LLM tagging

---

## Setup

**Windows / PowerShell, from the repo root.** You will use **Docker Compose**, a root **`.env`**, **`load-env.ps1`** (dot-sourced), and **Alembic migrations** run from **`tools_api`**.

**1. Environment file**

```powershell
Copy-Item .env.example .env
# edit .env so Postgres (and other vars) match what you want for Compose and local commands
```

**2. Dot-source env into your shell** (Compose uses the root `.env` for the stack; dot-sourcing is for **host** commands such as `uv run` in `tools_api`):

```powershell
. .\load-env.ps1
```

Use the leading `. ` so variables stay in your session.

**3. Docker Compose**

```powershell
docker compose up
```

**4. Alembic (migrations)** — from **`tools_api`**:

```powershell
cd tools_api
uv run invoke migrate
```

**5. MCP client** — wire your agent app (Cursor, Claude Desktop, etc.) to this server using either transport:

- **Streamable HTTP:** `http://localhost:8765/mcp` when the Compose **`tools_mcp`** service is running (use `http://<host>:<TOOLS_MCP_PORT>/mcp` if you changed the port in `.env`).
- **Stdio:** from **`tools_api`** with the same environment loaded, run `uv run python -m app.cmd.serve_mcp.stdio` and configure the client to launch that command (see the client’s MCP docs).

Optional: [MCP Inspector](http://localhost:6274) (Compose) to try tools against the HTTP endpoint.

**6. Catalog (MTGJSON)** — in the agent chat, ask it to **fetch the latest MTGJSON** / refresh the local card catalog (it should use this server’s MTGJSON MCP tools and App). Operator-oriented details: [docs/DB-POPULATE-PLAN.md](docs/DB-POPULATE-PLAN.md).

Deck and inventory behavior for agents: [tasks/deck-building-instructions.md](tasks/deck-building-instructions.md).

---

## Repo layout (overview)

```
magic-boto/
├── docker-compose.yml
├── load-env.ps1
├── .env.example
├── AGENTS.md
├── docs/
├── tasks/
├── tools-ui/      # MCP App frontends (built into the server)
└── tools_api/     # server, worker, database migrations
```

---

## Development notes

- **No auto `.env` loading:** the app reads the process environment only; load `.env` into your shell first.
- **Commit pattern:** services never call `commit()`; the route or tool handler does.
- **MCP-first usage:** prefer MCP tools and Apps for catalog, inventory, and tagging flows.
- **Platform:** same as Stack (Windows-focused repo today).
