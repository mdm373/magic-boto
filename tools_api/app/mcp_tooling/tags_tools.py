"""MCP tag tool registrations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from app.api_schema.tag_schema import Tag
from app.errors import InvalidRequestError, NotFoundError
from app.repository import CardTagEntry, TagRepo
from app.services import create_tag_service
from app.services.tag_sweep_initializer import SweepKickoffRequest, create_tag_sweep_initializer
from app.worker import enqueue_materialize_sweep_batches

from .error_middleware import AppMcp


class SweepEnqueueResult(BaseModel):
    sweep_id: str


_tag_service = create_tag_service()
_tag_repo = TagRepo()
_sweep_initializer = create_tag_sweep_initializer()


def register_tags_tools(app_mcp: AppMcp) -> None:
    """Register tag MCP tools."""

    @app_mcp.tool(
        name="list_tags",
        description=(
            "List all user-defined tags. Tags have descriptions indicating their intent"
            "Tags can be applied to cards to organise them by intent or theme."
        ),
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
        sweep_include_types: Annotated[
            list[str],
            Field(
                description=(
                    "Card types the sweep should be restricted to "
                    "(e.g. ['creature', 'artifact']). Omit or pass empty to sweep all types."
                ),
            ),
        ] = [],
        sweep_include_supertypes: Annotated[
            list[str],
            Field(
                description=(
                    "Card supertypes the sweep should be restricted to "
                    "(e.g. ['legendary']). Omit or pass empty to sweep all supertypes."
                ),
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
        name="tag_cards",
        description=(
            "Apply a tag to one or more cards by oracle ID. "
            "Use ``oracle_id`` from card search results."
        ),
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
            Field(description="List of oracle IDs of the cards to tag."),
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
        description=(
            "Remove a tag from one or more cards by oracle ID. "
            "The tag is lifted from the card identity, affecting all printings."
        ),
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
            Field(description="List of oracle IDs of the cards to untag."),
        ],
    ) -> Literal["ok"]:
        async with app_mcp.session() as session:
            ok = await _tag_service.remove_card_tags(session, tag_name, oracle_ids)
            if not ok:
                raise NotFoundError(f"Tag '{tag_name}' not found.")
        return "ok"

    @app_mcp.tool(
        name="enqueue_tag_sweep",
        description=(
            "Trigger an async sweep that evaluates eligible cards against the tag description "
            "and applies the tag to matches. "
            "Always ask the user how many cards to sweep (limit) before calling this tool — "
            "do not assume or infer a value."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def enqueue_tag_sweep(
        tag_name: Annotated[str, Field(description="Tag name to sweep (must exist).")],
        limit: Annotated[
            int,
            Field(
                description=(
                    "Number of cards to sweep. Must be explicitly provided by the user — "
                    "do not default or infer this value. "
                    "0 means the entire eligible catalog (can be tens of thousands of cards)."
                ),
                ge=0,
            ),
        ],
        audit_after: Annotated[
            bool,
            Field(description="Run an audit sweep automatically after processing completes."),
        ] = True,
    ) -> SweepEnqueueResult:
        request = SweepKickoffRequest(
            tag_name=tag_name,
            include_unsure=True,
            include_excluded=True,
            audit_after=audit_after,
        )
        async with app_mcp.session() as session:
            sweep = await _sweep_initializer.init_sweep(session, request)
            sweep_id = sweep.id

        enqueue_materialize_sweep_batches(
            str(sweep_id),
            tag_name,
            limit=limit,
            reenqueue_failed=False,
        )
        return SweepEnqueueResult(sweep_id=str(sweep_id))
