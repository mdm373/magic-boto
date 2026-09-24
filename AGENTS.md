# Agent instructions

Guidance for AI agents (Claude Code, Cursor, etc.) working in this repo.

> **Never edit `CLAUDE.md`** — it imports this file. All changes go here in `AGENTS.md`.

## Environment

Copy `.env.example` to `.env` at the project root and fill in values. Load it into your shell once before running any invoke tasks:

```powershell
. .\scripts\load-env.ps1   # dot-source from the project root
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

## Deployment (Fly.io)

The CLI binary is **`flyctl`**, not `fly` — `fly` is not on PATH in this environment (in PowerShell, Bash, or otherwise). Every `fly ...` command referenced below (`fly deploy`, `fly logs`, `fly machine status`, etc.) means `flyctl ...` in practice.

**Never run a deploy yourself** — `<service>\deploy.ps1`, `fly deploy`, or anything that ends up invoking either (a `release_command` migration included), for any reason, including to troubleshoot or diagnose a live issue. This holds even mid-debugging-session, even when you're confident the fix is right, even when the user asked you to build or fix the deploy config. Diagnose with read-only commands instead — `fly logs`, `fly machine status`/`--display-config`, `fly ssh console`, `fly secrets list`, `fly config validate` — and read-only or clearly-scoped-reversible probes like `fly machine run`/`fly machine start` against a *stopped* machine when you need to see it boot. Propose the fix, explain what you'd run, and wait for the user to explicitly say to deploy it — every single time, not just the first.

Stateful backing services (**`postgres/`**, **`redis/`**) each get their own directory holding **one `Dockerfile` shared by both stacks**: root `docker-compose.yml` builds it locally (`build: ./postgres`, `build: ./redis`) and `<service>/fly.toml` + `<service>/deploy.ps1` deploy that same image to Fly. When adding or changing one of these services, edit the shared `Dockerfile` once — never fork it into a separate local vs. prod copy, and never let `docker-compose.yml` pull a stock image (e.g. `image: redis:7-alpine`) for a service that also has a Fly deploy, since that reintroduces the exact drift this layout exists to avoid.

Deploy scripts stay thin wrappers around the shared logic in **`scripts/fly-deploy.ps1`** (the `Deploy-FlyApp` function: idempotent app/volume/secrets/deploy, volume optional) and **`scripts/get-env-value.ps1`** (parses `.env`-style files). A new `<service>/deploy.ps1` should dot-source both and call `Deploy-FlyApp`, not reimplement app/volume-existence checks; it prints its own final "reachable at ..." line since that differs per app. `Deploy-FlyApp` does **not** force a machine count per process group — an earlier version ran `fly scale count <group>=1` after every deploy to collapse Fly's default 2-machine-per-group redundancy down to one, but Fly's second machine in that pair is a **standby** (`FLY_STANDBY_FOR` env var pointing at the primary's machine ID, boots `stopped` by design, only activates if the primary crashes), not an active duplicate — destroying the primary via `fly scale count` can non-deterministically leave the *standby* as the survivor, which then sits `stopped` forever pointing at a now-destroyed primary and never runs anything (this is exactly what happened to `tools_api`'s `worker` group: it silently had zero live Celery workers). Leave Fly's default redundancy alone; if a process group truly must run as a single machine, scale it down by hand after confirming with `fly machine list` which one is the standby.

**Public + private split on one app:** if a future service needs some endpoints public and others admin-only-private, don't split it into two Fly apps — use one image with two Fly **process groups** (`[processes]` in `fly.toml`, one Machine per group) and give only the public-facing process group's `[[services]]` block a `[[services.ports]]` entry; a group with no `[[services.ports]]` stays reachable only over the private network (`.internal`)/WireGuard even though the app has a public IP for the other group. Filter at the app layer too, as defense in depth, not as the only control — the network-level split is what actually keeps something off the internet. `authelia/` doesn't need this (no separate admin surface to hide — the login portal and the OIDC endpoints Claude uses are the same surface), so it's a single process group; reach for the split only when a service actually has an admin-only surface worth hiding.

**Auth (`authelia/`):** Authelia is the OIDC provider backing `tools_api`'s MCP resource-server auth gate (`tools_api/app/mcp_tooling/auth/`, generic `Oidc*` naming — not tied to any one provider) and Claude's MCP connector. It's stateless (session/consent/token state lives in the `magicboto_authelia` database on the shared `magic-boto-db` Postgres instance over `.internal`, same same-instance-sibling-database pattern as any other service that doesn't need its own Postgres + volume). Every real secret lives as a gitignored file under `authelia/.secrets/` (generated/prompted by `authelia\generate-secrets.ps1`) — **never** as a literal or a Fly *secret* (env var) for anything multi-line: `fly secrets set` takes the value as a CLI argument, and PowerShell's argument marshaling to `flyctl.exe` silently corrupts multi-line values (the OIDC issuer's RSA key) passed that way, hanging the Machine at boot on the corrupted file instead of failing cleanly. Two distinct mechanisms consume those files, and picking the right one matters:
  - **Authelia's own env-var config binding** (`AUTHELIA_<PATH>` / `AUTHELIA_<PATH>_FILE` for secret-shaped keys — real, documented Authelia behavior) for any value that's a plain scalar under a fixed key path: `session.secret`, `storage.encryption_key`, `identity_providers.oidc.hmac_secret`/`issuer_private_key`, `identity_validation.reset_password.jwt_secret`, `storage.postgres.address/username/password`. These are simply omitted from `configuration.yml` entirely and set via `authelia/fly.toml`'s `[env]` (Fly) / `docker-compose.yml`'s `environment:` (local) — `_FILE` variants point at the same paths `[[files]]`/bind-mounts deliver.
  - **`authelia/docker-entrypoint.sh`** — genuine `{{ VAR }}` Mustache-style interpolation (variables only, no sections/partials — a small `awk` script, no bash/extra package needed), run before `exec`'ing the base image's real entrypoint, for anything Authelia's env-var binding can't reach: [Authelia's docs](https://www.authelia.com/configuration/methods/secrets/) explicitly say list-of-object sections — `session.cookies[]`, `identity_providers.oidc.clients[]` — can't be set via env vars or secrets at all, so `client_secret` and the cookie `domain`/`authelia_url`/`default_redirection_url` go through this instead, along with `users_database.yml`'s dynamic username map key. `configuration.yml`/`users_database.yml` are themselves templates (baked into the image as `*.yml.template`; an earlier attempt at a built-in Authelia config-file template engine — `X_AUTHELIA_CONFIG_FILTERS=template` — doesn't exist/doesn't work in 4.38, this `awk` script is the real mechanism). `client_secret`/admin-password-hash are still genuinely secret and stay file-delivered (matching Authelia's own preferred convention) rather than becoming plain env vars: the entrypoint `export`s them from their files only for the render step, then `unset`s them before `exec`, so Authelia's own process never inherits them.
  - `authelia/fly.toml`'s `[[files]]` use `local_path` (read straight off disk at `fly deploy` time — same files feed both mechanisms above), never `secret_name`, for exactly the multi-line-corruption reason above.
  - `.env` holds only `AUTHELIA_ADMIN_USERNAME`/`AUTHELIA_ADMIN_EMAIL` — your identity, not a secret.
  Run `authelia\generate-secrets.ps1` (or just `authelia\deploy.ps1`, which calls it — every deploy, not just the first) to populate `.env` and `authelia/.secrets/`. The internal secrets and the Claude connector's client secret only ever generate once; your admin username/email/password are always re-prompted instead, since that's your own login you might want to change later — leave a prompt blank to keep the current value. Never hand-write a secret, hash, or path into either YAML file, and never add a new `{{ }}`-style placeholder expecting Authelia to expand it — use one of the two real mechanisms above.

**`tools_api/` (MCP + Celery worker):** two process groups from one image, deployed via `tools_api/fly.toml` + `tools_api/deploy.ps1` — the plain HTTP API (`app.cmd.serve_http`) is never deployed to Fly at all, only `mcp` (`app.cmd.serve_mcp.asgi`, public, `TOOLS_MCP_AUTH_ENABLED=true` — bearer tokens checked against the deployed Authelia instance) and `worker` (Celery). `worker` has **no `[[services]]` block whatsoever** — not even a private one — since it only ever makes outbound connections to Postgres/Redis and is never reached by anything; that's a simpler variant of the public/private split above for when the private side needs zero reachability, not just non-public reachability. `fly.toml`'s `[deploy] release_command` runs `uv run invoke migrate` once, on its own temporary machine, before every deploy's new machines take over — a failed migration aborts the whole deploy and leaves the previous release running, so this is safe to leave automatic (unlike an agent running migrations ad hoc, which still needs your confirmation per the Python section below). `deploy.ps1` builds `tools-ui` (`npm install && npm run build`, writing into `app/mcp_tooling/ui_dist/`) *before* calling `fly deploy` — there's no Dockerfile change for this, since local dev already gets `ui_dist` the same way (via docker-compose's bind mount) and the existing `COPY . .` just picks up whatever's on disk at build-context-upload time.

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
