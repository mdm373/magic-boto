"""DB-related tasks."""

from invoke import Context, task


@task(default=True)
def migrate(c: Context) -> None:
    """Run Alembic migrations (upgrade head)."""
    c.run("uv run alembic upgrade head")
