"""HTTP routes for user-defined tags."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema.tag_schema import CardTagRequest, CreateTagRequest, Tag
from app.db import get_async_session
from app.errors import InvalidRequestError, NotFoundError
from app.repository import CardTagEntry, TagRepo
from app.services import create_tag_service


def create_tag_router() -> APIRouter:
    service = create_tag_service()
    tag_repo = TagRepo()
    router = APIRouter(
        prefix="/tags",
        tags=["tags"],
    )

    @router.get(
        "",
        response_model=list[Tag],
        operation_id="list_tags",
        summary="List all tags",
    )
    async def list_tags(
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> Sequence[Tag]:
        return await tag_repo.list_tags(session)

    @router.get(
        "/{name}",
        response_model=Tag,
        operation_id="get_tag",
        summary="Get a tag by name",
    )
    async def get_tag(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        name: Annotated[str, Path()],
    ) -> Tag:
        tag = await tag_repo.get_tag(session, name)
        if tag is None:
            raise NotFoundError(f"Tag '{name}' not found.")
        return tag

    @router.post(
        "",
        response_model=Tag,
        status_code=201,
        operation_id="create_tag",
        summary="Create a tag",
    )
    async def create_tag(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        body: CreateTagRequest,
    ) -> Tag:
        canonical = body.name.strip().lower()
        if not canonical:
            raise InvalidRequestError("Tag name is required.")
        if not body.description.strip():
            raise InvalidRequestError("Tag description is required.")
        existing = await tag_repo.get_tag(session, canonical)
        if existing is not None:
            raise InvalidRequestError(f"Tag '{canonical}' already exists.")
        tag = await tag_repo.create_tag(
            session,
            canonical,
            body.description,
            sweep_include_types=body.sweep_include_types,
            sweep_include_supertypes=body.sweep_include_supertypes,
        )
        await session.commit()
        return tag

    @router.delete(
        "/{name}",
        status_code=204,
        operation_id="delete_tag",
        summary="Delete a tag",
    )
    async def delete_tag(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        name: Annotated[str, Path()],
    ) -> None:
        deleted = await tag_repo.delete_tag(session, name)
        if not deleted:
            raise NotFoundError(f"Tag '{name}' not found.")
        await session.commit()

    @router.post(
        "/{name}/cards",
        status_code=204,
        operation_id="tag_cards",
        summary="Apply a tag to cards by oracle ID",
    )
    async def tag_cards(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        name: Annotated[str, Path()],
        body: CardTagRequest,
    ) -> None:
        ok = await service.add_card_tags(
            session, name, [CardTagEntry(oracle_id=oid) for oid in body.oracle_ids]
        )
        if not ok:
            raise NotFoundError(f"Tag '{name}' not found.")
        await session.commit()

    @router.delete(
        "/{name}/cards",
        status_code=204,
        operation_id="untag_cards",
        summary="Remove a tag from cards by oracle ID",
    )
    async def untag_cards(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        name: Annotated[str, Path()],
        body: CardTagRequest,
    ) -> None:
        ok = await service.remove_card_tags(session, name, body.oracle_ids)
        if not ok:
            raise NotFoundError(f"Tag '{name}' not found.")
        await session.commit()

    return router
