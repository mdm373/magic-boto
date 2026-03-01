"""Invoke task collection. Run from api/: uv run invoke server.start, db.migrate, verify, test.

Repo-root .env is loaded when the collection is loaded (before any task runs).
"""

from invoke import Collection

from tasks import db, server, test, verify
from tasks._env import load_repo_env

# Load env once when Invoke imports this module; all tasks run in the same process.
load_repo_env()

ns = Collection()
ns.add_collection(Collection.from_module(server), name="server", default=True)  # type: ignore[no-untyped-call]
ns.add_collection(Collection.from_module(db), name="db")  # type: ignore[no-untyped-call]
ns.add_collection(Collection.from_module(test), name="test")  # type: ignore[no-untyped-call]
ns.add_collection(Collection.from_module(verify), name="verify")  # type: ignore[no-untyped-call]
