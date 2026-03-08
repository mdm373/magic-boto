"""Invoke task collection. Run from agent_api/: uv run invoke serve.local, etc."""

from types import ModuleType
from typing import cast

from invoke import Collection

from tasks import build, lint, serve


def _from_module(module: ModuleType) -> Collection:
    return cast(Collection, Collection.from_module(module))  # type: ignore[no-untyped-call]


ns = Collection()
ns.add_collection(_from_module(build), name="build")
ns.add_collection(_from_module(serve), name="serve", default=True)
ns.add_collection(_from_module(lint), name="lint")
