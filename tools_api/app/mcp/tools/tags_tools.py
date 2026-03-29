"""MCP tag tool registrations."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from app.db import get_async_session_factory
from app.errors import InvalidRequestError, NotFoundError
from app.mcp.error_middleware import AppMcp
from app.schema.tag_schema import Tag
from app.services import create_tag_service
from mcp.types import ToolAnnotations

_tag_service = create_tag_service()


def register_tags_tools(app_mcp: AppMcp) -> None:
    """Register tag MCP tools."""

    @app_mcp.tool(
        name="list_tags",
        description=(
            "List all user-defined tags. "
            "Tags can be applied to cards to organise them by intent or theme."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_tags() -> list[Tag]:
        factory = get_async_session_factory()
        async with factory() as session:
            return await _tag_service.list_tags(session)

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
        factory = get_async_session_factory()
        async with factory() as session:
            tag = await _tag_service.get_tag(session, name)
        if tag is None:
            raise NotFoundError(f"Tag '{name}' not found.")
        return tag

    @app_mcp.tool(
        name="create_tag",
        description=(
            "Create a new tag with a name and description. "
            "Names are stored trimmed and lowercased. "
            "Raises an error if a tag with that name already exists."
        ),
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
            Field(description="Tag name (e.g. 'ramp', 'removal'). Stored lowercase."),
        ],
        description: Annotated[
            str,
            Field(description="Description of the tag's intent for the agent to understand."),
        ],
    ) -> Tag:
        canonical = name.strip().lower()
        if not canonical:
            raise InvalidRequestError("Tag name is required.")
        if not description.strip():
            raise InvalidRequestError("Tag description is required.")
        factory = get_async_session_factory()
        async with factory() as session:
            existing = await _tag_service.get_tag(session, canonical)
            if existing is not None:
                raise InvalidRequestError(f"Tag '{canonical}' already exists.")
            tag = await _tag_service.create_tag(session, canonical, description)
            await session.commit()
        return tag

    @app_mcp.tool(
        name="delete_tag",
        description="Delete a tag by name. Returns ok if deleted, raises an error if not found.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def delete_tag(
        name: Annotated[str, Field(description="Tag name to delete (case-insensitive).")],
    ) -> Literal["ok"]:
        factory = get_async_session_factory()
        async with factory() as session:
            deleted = await _tag_service.delete_tag(session, name)
            if not deleted:
                raise NotFoundError(f"Tag '{name}' not found.")
            await session.commit()
        return "ok"
