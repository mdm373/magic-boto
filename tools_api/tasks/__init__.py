"""Invoke task collection. Run from tools_api/.

Examples: ``uv run invoke serve.local``, ``uv run invoke import.inventory``.
"""

from types import ModuleType
from typing import cast

from invoke import Collection

from tasks import (
    _delete,
    _export,
    _import,
    _restore,
    audit,
    build,
    fetch,
    lint,
    migrate,
    serve,
    sweep,
)


def _from_module(module: ModuleType) -> Collection:
    return cast(Collection, Collection.from_module(module))  # type: ignore[no-untyped-call]


ns = Collection()
ns.add_collection(_from_module(audit), name="audit")
ns.add_collection(_from_module(build), name="build")
ns.add_collection(_from_module(serve), name="serve", default=True)
ns.add_collection(_from_module(migrate), name="migrate")
ns.add_collection(_from_module(lint), name="lint")
ns.add_collection(_from_module(fetch), name="fetch")
ns.add_collection(_from_module(_export), name="export")
ns.add_collection(_from_module(_import), name="import")
ns.add_collection(_from_module(_restore), name="restore")
ns.add_collection(_from_module(_delete), name="delete")
ns.add_collection(_from_module(sweep), name="sweep")
