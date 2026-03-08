"""Build tasks. Run from agent_api/."""

from invoke import Context, task


@task
def local(c: Context) -> None:
    """Sync local dependencies."""
    c.run("uv sync")


@task
def docker(c: Context) -> None:
    """Rebuild the Agent API Docker image (no cache)."""
    c.run("docker compose -f ../docker-compose.yml build --no-cache agent_api")


@task(default=True, pre=[local, docker])
def all(c: Context) -> None:
    """Run local uv sync then Docker agent_api rebuild."""
    pass
