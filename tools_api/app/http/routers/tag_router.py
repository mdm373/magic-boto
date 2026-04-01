"""HTTP routes for user-defined tags."""

from fastapi import APIRouter, Depends
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.errors import InvalidRequestError, NotFoundError
from app.schema.tag_schema import CardTagRequest, CreateTagRequest, Tag
from app.services import create_tag_service
from app.services.tag_service import CardTagEntry


def create_tag_router() -> APIRouter:
    service = create_tag_service()
    router = APIRouter(
        prefix="/tags",
        tags=["tags"],
        dependencies=[Depends(inject_session_into_request)],
    )

    @router.get(
        "",
        response_model=list[Tag],
        operation_id="list_tags",
        summary="List all tags",
    )
    async def list_tags(request: Request) -> list[Tag]:
        session = get_request_session(request)
        return await service.list_tags(session)

    @router.get(
        "/{name}",
        response_model=Tag,
        operation_id="get_tag",
        summary="Get a tag by name",
    )
    async def get_tag(name: str, request: Request) -> Tag:
        session = get_request_session(request)
        tag = await service.get_tag(session, name)
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
    async def create_tag(body: CreateTagRequest, request: Request) -> Tag:
        canonical = body.name.strip().lower()
        if not canonical:
            raise InvalidRequestError("Tag name is required.")
        if not body.description.strip():
            raise InvalidRequestError("Tag description is required.")
        session = get_request_session(request)
        existing = await service.get_tag(session, canonical)
        if existing is not None:
            raise InvalidRequestError(f"Tag '{canonical}' already exists.")
        tag = await service.create_tag(
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
    async def delete_tag(name: str, request: Request) -> None:
        session = get_request_session(request)
        deleted = await service.delete_tag(session, name)
        if not deleted:
            raise NotFoundError(f"Tag '{name}' not found.")
        await session.commit()

    @router.post(
        "/{name}/cards",
        status_code=204,
        operation_id="tag_cards",
        summary="Apply a tag to cards by oracle ID",
    )
    async def tag_cards(name: str, body: CardTagRequest, request: Request) -> None:
        session = get_request_session(request)
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
    async def untag_cards(name: str, body: CardTagRequest, request: Request) -> None:
        session = get_request_session(request)
        ok = await service.remove_card_tags(session, name, body.oracle_ids)
        if not ok:
            raise NotFoundError(f"Tag '{name}' not found.")
        await session.commit()

    return router
