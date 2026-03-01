"""Verify task: delegate to check, lint, then test."""

from invoke import Context, task

from tasks import check as check_tasks
from tasks import lint as lint_tasks
from tasks import test as test_tasks


@task(default=True)
def run(c: Context) -> None:
    """Run check (ruff), lint (mypy + import-lint), and test (full verify)."""
    check_tasks.run(c)
    lint_tasks.all(c)
    test_tasks.run(c)
