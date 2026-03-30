"""Migrate task: run database migrations."""

import json

from invoke import Context, Exit, task


@task(default=True)
def up(c: Context) -> None:
    """Run Alembic migrations (upgrade head)."""

    c.run("uv run alembic upgrade head")
    c.run("uv run invoke export.db-schema")


@task(help={"count": "Number of revisions to roll back (default: 1)."})
def down(c: Context, count: int = 1) -> None:
    """Run Alembic downgrade by N revisions (default 1)."""

    c.run(f"uv run alembic downgrade -{count}")
    c.run("uv run invoke export.db-schema")


@task()
def create(c: Context) -> None:
    """Create a new Alembic revision (prompts for revision message)."""

    message = input("Revision message: ").strip()

    if not message:
        raise Exit("Revision message is required.")

    c.run(f"uv run alembic revision -m {json.dumps(message)}")
