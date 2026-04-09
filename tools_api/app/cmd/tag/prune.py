"""CLI entrypoint: prune side tags and audits for a tag without deleting the tag itself."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.db import AsyncSqlalchemyResources, sqlalchemy_resources_lifespan
from app.repository.tag_audit_repo import TagAuditRepo
from app.repository.tag_repo import TagRepo
from app.repository.tag_sweep_repo import TagSweepRepo

_tag_repo = TagRepo()
_audit_repo = TagAuditRepo()
_sweep_repo = TagSweepRepo()


def _is_side_tag(name: str) -> bool:
    return name.endswith("_unsure") or name.endswith("_excluded")


async def _prune_one(
    resources: AsyncSqlalchemyResources,
    tag_name: str,
) -> None:
    async with resources.session_scope() as session:
        tag = await _tag_repo.require_tag_model(session, tag_name)

        for side_tag in (f"{tag_name}_unsure", f"{tag_name}_excluded"):
            if await _tag_repo.delete_tag(session, side_tag):
                logger.info("Deleted side tag '{}'.", side_tag)

        deleted_audits = await _audit_repo.delete_audits_for_tag(session, tag.id)
        if deleted_audits:
            logger.info("Deleted {} audit(s) for '{}'.", deleted_audits, tag_name)

        deleted_batches = await _sweep_repo.delete_sweep_batch_history_for_tag(session, tag.id)
        if deleted_batches:
            logger.info("Deleted {} sweep batch(es) for '{}'.", deleted_batches, tag_name)


async def _run(tag_name: str) -> None:
    async with sqlalchemy_resources_lifespan() as r:
        await _prune_one(r, tag_name)


async def _run_all() -> None:
    async with sqlalchemy_resources_lifespan() as r:
        async with r.session_scope() as session:
            tags = await _tag_repo.list_tags(session)

        primary = [t for t in tags if not _is_side_tag(t.name)]
        if not primary:
            logger.info("No tags to prune.")
            return

        logger.info("Pruning {} tag(s): {}", len(primary), ", ".join(t.name for t in primary))
        for tag in primary:
            await _prune_one(r, tag.name)


def main() -> None:
    args = sys.argv[1:]
    all_tags = "--all" in args
    args = [a for a in args if a != "--all"]

    if all_tags:
        if args:
            logger.error("Usage: python -m app.cmd.tag.prune --all")
            sys.exit(1)
        asyncio.run(_run_all())
    else:
        if len(args) != 1:
            logger.error("Usage: python -m app.cmd.tag.prune <tag_name>")
            sys.exit(1)
        asyncio.run(_run(args[0]))


if __name__ == "__main__":
    main()
