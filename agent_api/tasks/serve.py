"""Serve task: run the Agent API server. Run from agent_api/."""

import os

from invoke import Context, task

_COMPOSE = "docker compose -f ../docker-compose.yml"


@task(default=True)
def local(c: Context) -> None:
    """Start postgres and tools_api in Docker, then run agent uvicorn locally."""
    c.run(f"{_COMPOSE} up -d postgres tools_api")
    port = os.environ.get("AGENT_PORT", "8001")
    c.run(f"uv run uvicorn app.main:app --reload --host 0.0.0.0 --port {port}")


@task
def docker(c: Context) -> None:
    """Start stack detached, then run agent_api in foreground to watch logs."""
    c.run(f"{_COMPOSE} up -d")
    c.run(f"{_COMPOSE} up agent_api")
