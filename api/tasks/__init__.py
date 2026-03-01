"""Invoke task collection. Run from api/: uv run invoke serve.start, migrate, verify, test.

Repo-root .env is loaded when the collection is loaded (before any task runs).
"""

from types import ModuleType
from typing import cast

from invoke import Collection

from tasks import check, lint, migrate, serve, test, verify
from tasks._env import load_repo_env

# Load env once when Invoke imports this module; all tasks run in the same process.
load_repo_env()


def _from_module(module: ModuleType) -> Collection:
    """Build a Collection from a task module. Typed wrapper for Collection.from_module."""
    return cast(Collection, Collection.from_module(module))  # type: ignore[no-untyped-call]


ns = Collection()
ns.add_collection(_from_module(serve), name="serve", default=True)
ns.add_collection(_from_module(migrate), name="migrate")
ns.add_collection(_from_module(lint), name="lint")
ns.add_collection(_from_module(test), name="test")
ns.add_collection(_from_module(check), name="check")
ns.add_collection(_from_module(verify), name="verify")
