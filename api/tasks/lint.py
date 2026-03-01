"""Lint tasks: mypy (python) and import-linter (imports)."""

from invoke import Context, task


@task
def imports(c: Context) -> None:
    """Run import-linter."""
    c.run("uv run lint-imports")


@task
def python(c: Context) -> None:
    """Run mypy."""
    c.run("uv run mypy app migrations tasks --no-incremental")


@task(default=True)
def all(c: Context) -> None:
    """Run mypy and lint-imports."""
    python(c)
    imports(c)
