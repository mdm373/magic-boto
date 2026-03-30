"""MCP oracle tag sweep tool registrations."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from app.db import get_async_session_factory
from app.errors import InvalidRequestError, NotFoundError
from app.mcp.error_middleware import AppMcp
from app.schema.card_schema import TagSweepPage
from app.services import create_oracle_tag_sweep_service, create_tag_service
from app.services.mapper import CardMapper
from app.services.oracle_tag_sweep_service import SweepPage

_sweep_service = create_oracle_tag_sweep_service()
_tag_service = create_tag_service()
_card_mapper = CardMapper()


def _to_sweep_page(page: SweepPage, *, is_resume: bool = False) -> TagSweepPage:
    return TagSweepPage(
        is_resume=is_resume,
        cards=[_card_mapper.to_response(c) for c in page.cards],
        next_cursor=page.next_cursor,
        is_complete=page.is_complete,
    )


def register_oracle_tag_sweep_tools(app_mcp: AppMcp) -> None:
    """Register oracle tag sweep MCP tools."""

    @app_mcp.tool(
        name="start_tagging",
        description=(
            "Create a new tag and begin a sweep to find cards to apply it to. "
            "Returns the first page of cards pending review for this tag. "
            "Raises an error if the tag already exists — use resume_tagging instead."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def start_tagging(
        tag_name: Annotated[
            str,
            Field(description="Tag name to create (stored lowercase). E.g. 'flying', 'ramp'."),
        ],
        description: Annotated[
            str,
            Field(description="Description of the tag's intent for the agent to understand."),
        ],
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=200, description="Cards to return per page."),
        ] = 50,
    ) -> TagSweepPage:
        canonical = tag_name.strip().lower()
        if not canonical:
            raise InvalidRequestError("Tag name is required.")
        if not description.strip():
            raise InvalidRequestError("Tag description is required.")

        factory = get_async_session_factory()
        async with factory() as session:
            existing = await _tag_service.get_tag(session, canonical)
            if existing is not None:
                raise InvalidRequestError(
                    f"Tag '{canonical}' already exists. Use resume_tagging to continue sweeping."
                )
            await _tag_service.create_tag(session, canonical, description)
            page = await _sweep_service.start_sweep(session, canonical, limit)
            await session.commit()

        return _to_sweep_page(page)

    @app_mcp.tool(
        name="resume_tagging",
        description=(
            "Resume a previously started tag sweep from where it left off. "
            "Use this after a bot drops mid-sweep or to continue across sessions. "
            "Raises an error if no sweep exists for this tag — use start_tagging first."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def resume_tagging(
        tag_name: Annotated[str, Field(description="Tag name to resume (case-insensitive).")],
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=200, description="Cards to return per page."),
        ] = 50,
    ) -> TagSweepPage:
        factory = get_async_session_factory()
        async with factory() as session:
            page = await _sweep_service.resume_sweep(session, tag_name, limit)

        return _to_sweep_page(page, is_resume=True)

    @app_mcp.tool(
        name="push_tags",
        description=(
            "Apply tags to cards from the current sweep page, advance the cursor, "
            "and return the next page. "
            "Pass an empty oracle_ids list to advance without tagging any cards. "
            "When is_complete is True the sweep is finished and last_swept_at is recorded."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def push_tags(
        tag_name: Annotated[str, Field(description="Tag name (case-insensitive).")],
        oracle_ids: Annotated[
            list[str],
            Field(
                description=(
                    "Oracle IDs of cards from the current page to tag. "
                    "Pass an empty list if none of the cards qualify."
                )
            ),
        ],
        next_cursor: Annotated[
            str | None,
            Field(
                description=(
                    "The next_cursor value returned by the previous start_tagging, "
                    "resume_tagging, or push_tags call."
                )
            ),
        ],
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=200, description="Cards to return per page."),
        ] = 50,
    ) -> TagSweepPage:
        factory = get_async_session_factory()
        async with factory() as session:
            if oracle_ids:
                ok = await _tag_service.add_card_tags(session, tag_name, oracle_ids)
                if not ok:
                    raise NotFoundError(f"Tag '{tag_name}' not found.")

            page = await _sweep_service.advance_and_fetch(session, tag_name, next_cursor, limit)
            await session.commit()

        return _to_sweep_page(page)

    @app_mcp.tool(
        name="reset_tag_sweep",
        description=(
            "Reset the sweep state for a tag, forcing a full re-sweep on the next resume_tagging. "
            "Existing tag applications on cards are NOT removed. "
            "To wipe all tag applications and start fresh, delete the tag instead "
            "(cascades to sweep state and card tags), then call start_tagging."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def reset_tag_sweep(
        tag_name: Annotated[str, Field(description="Tag name to reset (case-insensitive).")],
    ) -> Literal["ok"]:
        factory = get_async_session_factory()
        async with factory() as session:
            await _sweep_service.reset_sweep(session, tag_name)
            await session.commit()
        return "ok"
