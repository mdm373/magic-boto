"""Build tasks: local uv sync and Docker tools_api image rebuild. Run from tools_api/."""

from invoke import Context, task


@task
def local(c: Context) -> None:
    """Sync local dependencies (uv sync)."""
    c.run("uv sync")


@task
def docker(c: Context) -> None:
    """Rebuild the Tools API Docker image (no cache)."""
    c.run("docker compose -f ../docker-compose.yml build --no-cache tools_api")


@task(default=True, pre=[local, docker])
def all(c: Context) -> None:
    """Run local uv sync then Docker tools_api rebuild."""
    pass
