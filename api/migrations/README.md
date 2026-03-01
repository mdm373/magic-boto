# Migrations

Migrations run against the same Postgres DB as the rest of the project. They use **POSTGRES_*** from the environment (e.g. load with `. ..\db\scripts\load-db-env.ps1` from repo root, or set in `.env`).

**From the `api/` directory:**

- Apply all migrations: `uv run alembic upgrade head`
- Roll back one: `uv run alembic downgrade -1`
- Current revision: `uv run alembic current`

First migration adds an index on `mtgjson."cardIdentifiers"("scryfallId")` for API lookups by Scryfall ID.
