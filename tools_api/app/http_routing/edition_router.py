"""MTGJSON v1 editions (sets) API: list and get by set code."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema import Edition, EditionsQuery
from app.db import get_async_session
from app.services import EditionQueryValidator, create_edition_service


def create_edition_router(validator: EditionQueryValidator) -> APIRouter:
    """
    Factory for MTGJSON edition routes.

    Uses closure-based DI for the validator and service.
    """

    service = create_edition_service()
    router = APIRouter(
        prefix="/edition",
        tags=["mtgjson_editions"],
    )

    @router.get(
        "",
        response_model=list[Edition],
        operation_id="list_editions",
        summary="Search for editions (sets)",
    )
    async def list_editions(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        set_code: str | None = Query(
            None,
            min_length=1,
            description="Exact edition/set code (e.g. M21).",
        ),
        name: str | None = Query(
            None,
            min_length=1,
            description="Fuzzy search on edition name (case-insensitive substring).",
        ),
    ) -> list[Edition]:
        query = EditionsQuery(set_code=set_code, name=name)
        query = validator.validate_edition_query(query)
        editions = await service.query_editions(session, query)
        return list(editions)

    @router.get(
        "/{set_code}",
        response_model=Edition,
        operation_id="get_edition",
        summary="Get one edition (set) by set code.",
    )
    async def get_edition_by_set_code(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        set_code: Annotated[str, Path()],
    ) -> Edition:
        edition = await service.get_edition(session, set_code)
        if edition is None:
            raise HTTPException(status_code=404, detail="Edition not found")
        return edition

    return router
