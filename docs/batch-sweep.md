# Batch Sweep

Replaces the synchronous, cursor-paged sweep (`app/tag/sweep/main.py`) with an
asynchronous pipeline built on the Anthropic Messages Batch API.

---

## Why

- **50 % cost reduction** from the Batch API discount, on top of the prompt-caching
  and compact-serialisation savings already in the codebase.
- **Eliminates Type 1 errors** (cross-card reason contamination) by sending one
  card per request — no batching of multiple cards in a single prompt.
- **Simplifies the response** to a single `"{verdict} {reason}"` line, removing
  JSON parsing complexity and reducing output tokens.

---

## Three tasks

```
sweep.kickoff --tag <name> [--limit N] [--oracle-ids-file path]
sweep.poll    --run-id <uuid> [--wait]
sweep.process --run-id <uuid> [--include-unsure] [--include-excluded]
```

App entrypoints live under `app/tag/kickoff/`, `app/tag/poll/`, `app/tag/process/`.
Task wiring lives in `tasks/sweep.py`.

### kickoff

1. Resolve the tag; load or create an **open** `sweep_runs` row for it (at most one
   open run per tag at a time).
2. Derive the epoch gate: `last_swept_at = MAX(triggered_at) WHERE tag_id=? AND status='complete'`.
   NULL on first-ever kickoff → all cards eligible.
3. Resume from `run.last_submitted_oracle_id` (NULL = start of catalogue).
4. Loop — each iteration:
   a. `fetch_all_pending(after=cursor, limit=min(BATCH_API_MAX, remaining))` — filters:
      type/supertype include lists, not-yet-tagged oracle IDs, and
      `MIN(card.created_at) > last_swept_at` (skips cards covered by prior complete runs).
      Ordered by `oracle_id`.
   b. If empty → mark run `complete`, exit.
   c. `client.beta.messages.batches.create(requests)` — one card per request,
      custom_id = oracle_id.
   d. **Immediately commit** (single transaction):
      `INSERT sweep_run_batches` + `UPDATE sweep_runs SET last_submitted_oracle_id`.
   e. Advance cursor; decrement remaining. If `--limit N` exhausted → exit (run
      stays open for the next kickoff call).

**Epoch gate assumption:** the card catalogue is not updated while a sweep run is
open. `triggered_at` is recorded when the run is created; the epoch gate for the
*next* run will be this timestamp. Any cards fetched into the catalogue must
therefore be ingested either before kickoff or after process completes, not
in between.

**Crash / partial failure:** if `batches.create()` throws on chunk N+1, chunks
1..N are already committed and their cards will not be re-submitted on retry.
If the DB commit throws after a successful `batches.create()`, the orphaned batch
is harmless — `add_card_tags` is idempotent and duplicate results are discarded.

**Re-enqueueing failures:** `--oracle-ids-file path` bypasses the cursor and
submits exactly the listed oracle IDs. Used to re-enqueue cards whose Batch API
request came back `errored` / `expired` from a previous process run.

### poll

Reads all `sweep_run_batches` for the run, calls
`client.beta.messages.batches.retrieve(batch_id)` for each non-terminal batch,
updates `status` and `completed_at` in the DB, and prints a status table.

With `--wait`: loops with a 30 s sleep until all batches reach a terminal state
(`ended`, `errored`, `expired`, `canceled`), then exits.

### process

1. Assert all batches for the run are terminal.
2. Stream results via `client.beta.messages.batches.results(batch_id)` for each
   `ended` batch.
3. Parse each result:
   - `succeeded` → `line.partition(" ")` → `(verdict, _, reason)`.
     Validate `verdict in {"tag", "unsure", "exclude"}`.
   - `errored / expired / canceled` or parse failure → collect oracle_id into
     `failed_ids`.
4. Bulk-apply tags via `tag_service.add_card_tags()` (and optionally the
   `_unsure` / `_excluded` side-tags).
5. Mark run `complete` (this `triggered_at` becomes the epoch gate for the next
   kickoff on this tag); if any `failed_ids`, write them to
   `debug/failed_ids_{run_id}.txt` and print the re-enqueue command.

---

## Response format

Each Batch API request carries one card as the user message (compact JSON,
oracle_id omitted — identity comes from custom_id). The system prompt asks for
exactly one line:

```
{verdict} {reason text}
```

where `verdict` is `tag`, `unsure`, or `exclude`. Parsing is a single
`str.partition(" ")` — no JSON, no schema validation.

The tag description (include / exclude rules) is in the system prompt with
`cache_control: {"type": "ephemeral"}`, matching the existing caching strategy.

---

## Schema

```sql
magic_boto.sweep_runs
  id                        UUID PK  DEFAULT gen_random_uuid()
  tag_id                    UUID NOT NULL  REFERENCES magic_boto.tags(id)  ON DELETE CASCADE
  triggered_at              TIMESTAMPTZ NOT NULL  DEFAULT now()
  status                    TEXT NOT NULL  DEFAULT 'open'
                            CHECK (status IN ('open', 'complete', 'failed'))
  last_submitted_oracle_id  TEXT   -- resume cursor; NULL = start of catalogue

magic_boto.sweep_run_batches
  id            UUID PK  DEFAULT gen_random_uuid()
  run_id        UUID NOT NULL  REFERENCES magic_boto.sweep_runs(id)  ON DELETE CASCADE
  batch_id      TEXT NOT NULL   -- Anthropic msgbatch_* ID
  status        TEXT NOT NULL  DEFAULT 'submitted'
                CHECK (status IN
                  ('submitted','in_progress','ended','errored','expired','canceling','canceled'))
  card_count    INT NOT NULL
  submitted_at  TIMESTAMPTZ NOT NULL  DEFAULT now()
  completed_at  TIMESTAMPTZ
```

No separate cursor table needed — `last_submitted_oracle_id` on `sweep_runs` is
the single source of truth for where the next kickoff should resume.

---

## New modules

```
app/tag/
  batch/
    client.py         submit_batch(), stream_results()
    system_prompt.md  single-card prompt
  kickoff/main.py
  poll/main.py
  process/main.py
app/services/
  sweep_run_service.py   create_run(), get_open_run(), record_batch(),
                         update_batch_status(), complete_run()
app/models/
  sweep_run.py
  sweep_run_batch.py
tasks/
  sweep.py
migrations/versions/
  YYYYMMDD_*_add_sweep_runs.py
```

---

## What is removed

- `app/tag/sweep/main.py` — synchronous sweep entrypoint
- `app/tag/sweep/user_prompt.md` — multi-card user prompt template
- `app/tag/sweep/claude_client.py` — `SweepClaudeClient` and helpers
- `app/services/oracle_tag_sweep_service.py` — replaced entirely by `sweep_run_service.py`
- `app/models/magic_boto_oracle_tag_sweep.py` — ORM model for the old state table
- Migration to drop `magic_boto.oracle_tag_sweep_state` (or equivalent table)

**Why `oracle_tag_sweep_service` is redundant:** it tracked two things — a paging
cursor and a `last_swept_at` epoch gate. `sweep_runs` covers both:
- cursor → `last_submitted_oracle_id` on the open run
- `last_swept_at` → `MAX(triggered_at) WHERE status = 'complete'` for the tag,
  queried inline in `fetch_all_pending`

The card eligibility query (`_fetch_page`) moves into `sweep_run_service.fetch_all_pending`.

`app/tag/sweep/system_prompt.md` is rewritten for single-card use and moved to
`app/tag/batch/system_prompt.md`. `app/tag/card_payload.py` is kept unchanged.

---

## Typical operator flow

```powershell
# Test with 50 cards
uv run invoke sweep.kickoff --tag ramp --limit 50
# → prints run_id

uv run invoke sweep.poll --run-id <id> --wait
uv run invoke sweep.process --run-id <id>

# Kick off the rest
uv run invoke sweep.kickoff --tag ramp
# → resumes from cursor, submits remaining cards in chunks

uv run invoke sweep.poll --run-id <id> --wait
uv run invoke sweep.process --run-id <id>

# If any failures were written to debug/failed_ids_<id>.txt:
uv run invoke sweep.kickoff --tag ramp --oracle-ids-file debug/failed_ids_<id>.txt
uv run invoke sweep.poll --run-id <id> --wait
uv run invoke sweep.process --run-id <id>
```
