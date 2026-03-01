"""Migrate task: run database migrations."""

from invoke import Context, task


@task(default=True)
def up(c: Context) -> None:
    """Run Alembic migrations (upgrade head)."""
    c.run("uv run alembic upgrade head")
