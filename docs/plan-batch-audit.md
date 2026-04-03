# Plan: Batch Audit Migration

Migrate tag auditing from a synchronous single-call workflow to the same async batch
pipeline used by sweeps. Introduces a shared `batches` table, a common batch service,
and shared poll logic reused by both sweep and audit task wrappers.

---

## Target schema

```
batches
  id, anthropic_batch_id, status, submitted_at, completed_at

tag_sweep
  id, tag_id (FK→tags), triggered_at, status

tag_sweep_batches
  id, tag_sweep_id (FK→tag_sweep), batch_id (FK→batches), card_count

tag_sweep_batch_cards
  id, tag_sweep_batch_id (FK→tag_sweep_batches), oracle_id, position, failed, chunk_custom_id

tag_audit
  id, tag_id (FK→tags), triggered_at, batch_id (FK→batches), report (TEXT nullable)
```

---

## Step 1 — Migration

Single migration file covering all schema changes atomically.

**Rename existing sweep tables:**
- `tag_sweep` → `tag_sweep`
- `sweep_run_batches` → `tag_sweep_batches`
  - rename column `run_id` → `tag_sweep_id`
  - drop columns `batch_id` (Anthropic ID), `status`, `submitted_at`, `completed_at` → move to `batches`
- `sweep_run_batch_cards` → `tag_sweep_batch_cards`
  - rename column `sweep_run_batch_id` → `tag_sweep_batch_id`

**New tables:**
- `batches` — extract the Anthropic batch lifecycle columns from `sweep_run_batches`
  - backfill from existing `sweep_run_batches` rows so no data is lost
  - add FK `tag_sweep_batches.batch_id → batches.id`
- `tag_audit` — new table: `tag_id`, `triggered_at`, `batch_id` (FK→batches), `report` (TEXT nullable); no status column

---

## Step 2 — ORM models

- `BatchModel` (`batches`) — `anthropic_batch_id`, `status` (BatchStatus), `submitted_at`, `completed_at`
- Update `SweepRunBatchModel` → rename class to `SweepBatchModel`, update table/column names, replace inline status/timestamp fields with `batch: Mapped[BatchModel]` relationship
- Update `SweepRunBatchCardModel` → rename class to `SweepBatchCardModel`, update FK column name
- `TagAuditModel` (`tag_audit`) — `tag_id`, `triggered_at`, `batch: Mapped[BatchModel]`, `report: Mapped[str | None]`
- Rename `SweepBatchStatus` enum → `BatchStatus` (shared); keep `SweepRunStatus` as-is

---

## Step 3 — Common batch service

New module: `app/services/batch_service.py`

Responsibilities:
- `create_batch(session, anthropic_batch_id) -> BatchModel` — insert and return
- `get_batch(session, batch_id) -> BatchModel`
- `get_batches_by_ids(session, ids) -> Sequence[BatchModel]`
- `update_batch_status(session, batch, status, completed_at) -> None`

Poll logic extracted here:

```python
async def poll_batches(
    session: AsyncSession,
    batches: Sequence[BatchModel],
    client: BatchApiClient,
) -> None:
```

Iterates batches, calls `client.get_batch_status()`, updates `status` + `completed_at`.
Commits are the caller's responsibility (service never commits).

---

## Step 4 — Update sweep service

`SweepRunService` changes:
- Update all references from old table/column names to new ones
- `record_batch_with_cards()` — now creates a `BatchModel` row first, then `SweepBatchModel` linked to it
- `get_non_terminal_batches()` — joins through `tag_sweep_batches → batches`, returns `Sequence[BatchModel]`
- `get_processable_batches()` — same join pattern
- `mark_batch_processed()` — operates on `SweepBatchModel`; `BatchModel.status` already ENDED

---

## Step 5 — Rename/update batch client

`app/tag/batch/client.py`:
- Rename `BatchSweepClient` → `BatchApiClient`
- No behavioral changes — methods already generic (`submit_batch`, `get_batch_status`, `get_results`)

---

## Step 6 — New audit service

New module: `app/services/tag_audit_service.py`

Responsibilities:
- `create_audit(session, tag_id) -> TagAuditModel`
- `get_open_audit(session, tag_id) -> TagAuditModel | None`
- `attach_batch(session, audit, batch) -> None` — sets `audit.batch_id`
- `finalize_audit(session, audit, report: str) -> None` — sets `audit.report`

No status column on `tag_audit` — state is fully inferred:
- `report IS NULL` + batch in progress → pending
- `report IS NULL` + batch ERRORED/EXPIRED/CANCELED → failed
- `report IS NOT NULL` → complete

---

## Step 7 — Audit app modules

`app/tag/audit/kickoff/main.py`
1. Fetch/create open `TagAuditModel` for the tag
2. Sample cards via `tag_service.sample_cards_for_tag()` (tagged / excluded / unsure)
3. Serialize with `card_to_dict()`, render user prompt template
4. Submit one request via `BatchApiClient.submit_batch()` → `anthropic_batch_id`
5. Create `BatchModel` via `batch_service.create_batch()`
6. Attach to audit via `tag_audit_service.attach_batch()`
7. Commit; print audit id

`app/tag/audit/poll/main.py`
1. Load `TagAuditModel` by id, eager-load `batch`
2. Pass `[audit.batch]` to `batch_service.poll_batches()`
3. Commit; print status

`app/tag/audit/process/main.py`
1. Load audit; verify `audit.batch.status == ENDED`
2. `BatchApiClient.get_results()` — one result, extract `content[0].text`
3. `tag_audit_service.save_report(session, audit, report)`
4. `tag_audit_service.complete_audit(session, audit)`
5. Commit
6. Write to `debug/{timestamp}_{tag}_audit.md`; open file

---

## Step 8 — Common poll task logic

New module: `tasks/batch_poll.py`

```python
def poll_until_done(c: Context, batch_ids: list[str], wait: bool) -> None:
```

Shared Invoke helper — knows nothing about sweep vs audit, just polls whatever
batch IDs it's given. Handles the `--wait` loop (30s interval until all terminal)
and the status table display.

Callers build the batch ID list differently:
- `sweep.poll --sweep-id <id>` — thin sweep helper queries `tag_sweep_batches` for
  all batch IDs belonging to that sweep, then calls `poll_until_done`
- `audit.poll --batch-id <id>` — passes `[batch_id]` directly

---

## Step 9 — Task wrappers

`tasks/audit.py` — new, mirrors `tasks/sweep.py` structure:
- `audit.kickoff --tag <name>`
- `audit.poll --batch-id <id> [--wait]`
- `audit.process --batch-id <id>`
- `audit.run --tag <name>` (kickoff → poll --wait → process)

`tasks/sweep.py` — update poll/process tasks to use `--batch-id` consistently; delegate poll to shared `batch_poll.py` helper.

---

## Implementation order

1. Migration file
2. ORM models (BatchModel, renamed sweep models, TagAuditModel)
3. `batch_service.py` with `poll_batches`
4. Update `SweepRunService` + rename `BatchSweepClient` → `BatchApiClient`
5. `tag_audit_service.py`
6. Audit kickoff / poll / process modules
7. `tasks/batch_poll.py` + `tasks/audit.py` + update `tasks/sweep.py`
8. Lint, type-check, update any broken imports
