# Populate the DB from MTG JSON — Plan

This doc captures how we populate and update the card catalog from MTGJSON. See also [PROJECT-PLAN.md](PROJECT-PLAN.md) for overall architecture.

---

## Decision: incremental (implement in two phases)

We will use the **incremental** approach for card data: **our own schema** and an ingest that can **upsert** from MTGJSON's per-set data (SetList.json + per-set JSON). Updates will then only fetch new or changed sets instead of re-downloading the full catalog. This is more complex, so we are **not** implementing the incremental update path yet.

- **Phase 1 (now):** Implement only the **initial load** — a script that gets the full card catalog into the DB once. No refresh script, no incremental update script.
- **Phase 2 (later):** Add the **incremental update** path (SetList + per-set fetch + upsert). Design is documented below.

---

## Why incremental (long-term)

- **Cheaper updates:** New sets = small downloads (SetList + a few set JSON files) and upserts; no full AllPrintings re-download.
- **Our schema:** We own the card/set table shape and keys (e.g. set code, card uuid) so we can upsert and add inventory in the same DB.
- **Same source:** MTGJSON's [v5 API](https://mtgjson.com/api/v5/) provides [SetList.json](https://mtgjson.com/downloads/all-files/) and [per-set JSON](https://mtgjson.com/api/v5/) (e.g. `MKM.json`); we use those for both initial load (all sets) and later incremental (only new/changed sets).

---

## Phase 1: implementation now (initial load only)

### 1. Add `tools_api/` DB tasks

- **`tools_api/tasks/populate.py`** — **Initial-load task only:**
  - Uses `POSTGRES_*` (or existing `PG*`) from env to build connection info.
  - Loads a local AllPrintings dump (`.psql`, `.psql.zip`, `.psql.gz`) into Postgres under schema `mtgjson` (one-time).
  - **Do not** implement refresh or incremental update in Phase 1.
- **`tools_api/debug/schema.sql`** — Optional schema dump to inspect MTGJSON tables/views during development (regenerate via `uv run invoke populate.schema`).
- **`tools_api/migrations/`** — App schema (e.g. `inventory`). If Phase 1 uses the pre-built .psql, catalog tables come from the dump; we add our schema and incremental ingest in Phase 2.

### 2. Initial-load options (Phase 1)

| Option | Phase 1 | Phase 2 (later) |
|--------|---------|------------------|
| **Pre-built .psql** | Script: download AllPrintings.psql.gz, decompress, `psql -f`. Catalog = mtgsqlive's schema. | Add our schema + ingest from per-set JSON; migrate or backfill from existing tables. |
| **Our schema + full JSON** | Migrations define our card/set tables. Script: download AllPrintings.json, parse, insert once. | Same schema; add SetList + per-set fetch + upsert script. |

**Recommendation for Phase 1:** Use **pre-built .psql** for the initial load (simplest). Document that Phase 2 will add our schema and the incremental ingest (SetList + per-set + upsert).

### 3. Document connection and run

- Ensure Postgres is up (`docker compose up -d`), copy `.env.example` to `.env`, then run the initial-load task once from `tools_api/`: `uv run invoke populate.mtg_json`. State that updates will be incremental later (not implemented yet).

---

## Data flow

**Phase 1 (now):** MTGJSON → download once → initial-load script → Postgres (one-time).

**Phase 2 (later):** SetList.json → diff → fetch only new/changed set JSON → upsert into our schema.

---

## Updating the DB when new cards come out (Phase 2, later)

We will **not** do a full refresh each time (too expensive). Updates will be **incremental**: fetch SetList, determine new or changed sets, fetch only those set JSON files, upsert into the catalog. Implement this in Phase 2; for now, no update path is implemented.

---

## Incremental updates — Phase 2 design (implement later)

- **SetList.json** — Small file listing all sets (set code, name, release date, etc.). Use it to see which sets exist and which are new or updated.
- **Per-set JSON** — Each set has its own file on the [v5 API](https://mtgjson.com/api/v5/) (e.g. `https://mtgjson.com/api/v5/MKM.json`). Only download the sets we don't already have (or that changed).
- **Our schema + upsert** — Our card/set tables and an ingest that **upserts** by stable keys (e.g. set code + card uuid). "Update" = fetch SetList, diff against DB, then for new/changed set codes fetch only those set JSON files and upsert. No full dump, no dropping the catalog.

**Data flow (Phase 2):** SetList.json → which sets new/changed? → fetch only those from API → parse and upsert → Postgres.
