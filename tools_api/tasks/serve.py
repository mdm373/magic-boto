"""Serve task: run the Tools API server. Run from tools_api/."""

import os

from invoke import Context, task

_COMPOSE = "docker compose -f ../docker-compose.yml"


@task(default=True)
def local(c: Context) -> None:
    """Start postgres in Docker, then run uvicorn locally. Port from TOOLS_API_PORT env."""
    c.run(f"{_COMPOSE} up -d postgres")
    port = os.environ.get("TOOLS_API_PORT", "8000")
    c.run(f"uv run uvicorn app.main:app --reload --host 0.0.0.0 --port {port}")


@task
def docker(c: Context) -> None:
    """Start stack detached, then run tools_api in foreground to watch logs."""
    c.run(f"{_COMPOSE} up -d")
    c.run(f"{_COMPOSE} up tools_api")
