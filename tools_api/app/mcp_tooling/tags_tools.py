"""MCP tag tool registrations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from app.api_schema.tag_schema import Tag
from app.errors import InvalidRequestError, NotFoundError
from app.repository import CardTagEntry, TagRepo
from app.services import create_tag_service

from .error_middleware import AppMcp

_tag_service = create_tag_service()
_tag_repo = TagRepo()


def register_tags_tools(app_mcp: AppMcp) -> None:
    """Register tag MCP tools."""

    @app_mcp.tool(
        name="list_tags",
        description="List tags with names, descriptions, and sweep filter settings.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_tags() -> Sequence[Tag]:
        async with app_mcp.session() as session:
            return await _tag_repo.list_tags(session)

    @app_mcp.tool(
        name="get_tag",
        description="Retrieve a single tag by name.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_tag(
        name: Annotated[str, Field(description="Tag name (case-insensitive).")],
    ) -> Tag:
        async with app_mcp.session() as session:
            tag = await _tag_repo.get_tag(session, name)
        if tag is None:
            raise NotFoundError(f"Tag '{name}' not found.")
        return tag

    @app_mcp.tool(
        name="create_tag",
        description="Create a tag (name stored trimmed/lowercase; error if it already exists).",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def create_tag(
        name: Annotated[
            str,
            Field(description="Tag name (stored lowercase)."),
        ],
        description: Annotated[
            str,
            Field(description="What this tag means for sweeps and tagging."),
        ],
        sweep_include_types: Annotated[
            list[str],
            Field(
                description="Restrict sweeps to these card types; empty = all types.",
            ),
        ] = [],
        sweep_include_supertypes: Annotated[
            list[str],
            Field(
                description="Restrict sweeps to these supertypes; empty = all.",
            ),
        ] = [],
    ) -> Tag:
        canonical = name.strip().lower()
        if not canonical:
            raise InvalidRequestError("Tag name is required.")
        if not description.strip():
            raise InvalidRequestError("Tag description is required.")
        async with app_mcp.session() as session:
            existing = await _tag_repo.get_tag(session, canonical)
            if existing is not None:
                raise InvalidRequestError(f"Tag '{canonical}' already exists.")
            tag = await _tag_repo.create_tag(
                session,
                canonical,
                description,
                sweep_include_types=sweep_include_types,
                sweep_include_supertypes=sweep_include_supertypes,
            )
        return tag

    @app_mcp.tool(
        name="update_tag",
        description="Update a tag's description (name matched case-insensitively).",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def update_tag(
        name: Annotated[
            str,
            Field(description="Tag name to update (case-insensitive)."),
        ],
        description: Annotated[
            str,
            Field(description="Replacement description text."),
        ],
    ) -> Tag:
        if not description.strip():
            raise InvalidRequestError("Tag description is required.")
        async with app_mcp.session() as session:
            ok = await _tag_repo.update_description(session, name, description)
            if not ok:
                raise NotFoundError(f"Tag '{name}' not found.")
            updated = await _tag_repo.get_tag(session, name)
        if updated is None:
            raise NotFoundError(f"Tag '{name}' not found.")
        return updated

    @app_mcp.tool(
        name="tag_cards",
        description="Attach a tag to oracle ids (from card search when verbose).",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def tag_cards(
        tag_name: Annotated[str, Field(description="Tag name to apply (case-insensitive).")],
        oracle_ids: Annotated[
            list[str],
            Field(description="Oracle ids to tag."),
        ],
    ) -> Literal["ok"]:
        async with app_mcp.session() as session:
            ok = await _tag_service.add_card_tags(
                session, tag_name, [CardTagEntry(oracle_id=oid) for oid in oracle_ids]
            )
            if not ok:
                raise NotFoundError(f"Tag '{tag_name}' not found.")
        return "ok"

    @app_mcp.tool(
        name="untag_cards",
        description="Remove a tag from oracle ids (oracle identity, all printings).",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def untag_cards(
        tag_name: Annotated[str, Field(description="Tag name to remove (case-insensitive).")],
        oracle_ids: Annotated[
            list[str],
            Field(description="Oracle ids to untag."),
        ],
    ) -> Literal["ok"]:
        async with app_mcp.session() as session:
            ok = await _tag_service.remove_card_tags(session, tag_name, oracle_ids)
            if not ok:
                raise NotFoundError(f"Tag '{tag_name}' not found.")
        return "ok"
