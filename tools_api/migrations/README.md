# Alembic migrations (`tools_api/migrations/`)

## Apply or revert

From **`tools_api/`**:

```powershell
uv run invoke migrate          # upgrade to head
uv run invoke migrate.down     # downgrade one revision
uv run invoke migrate.create   # new revision (prompts for message)
```

Or directly:

```powershell
uv run alembic upgrade head
uv run alembic downgrade -1
```

**Do not run upgrades or downgrades against a shared database unless the project owner confirms.**

## Layout

- **`alembic.ini`** — Alembic config (paths relative to `tools_api/`).
- **`versions/`** — one file per revision: `YYYYMMDD_<rev>_<slug>.py`.
- **`check_constraints.py`** — helpers for `TEXT` + `CHECK` “enum” columns (see existing revisions).

## Reference schema dump

After migrating a local DB, you can refresh the checked-in snapshot:

```powershell
uv run invoke export.db-schema
```

Writes `tools_api/debug/schema.sql` (do not hand-edit; regenerate only).
