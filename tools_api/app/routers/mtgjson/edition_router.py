"""MTGJSON v1 editions (sets) API: list and get by set code."""

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.requests import Request

from app.db import get_request_session, inject_session_into_request
from app.schema import EditionsQuery, MtgjsonEdition
from app.services import create_edition_service
from app.validators import EditionQueryValidator


def create_edition_router(validator: EditionQueryValidator) -> APIRouter:
    """
    Factory for MTGJSON edition routes.

    Uses closure-based DI for the validator and service.
    """

    service = create_edition_service()
    router = APIRouter(
        prefix="/edition",
        tags=["mtgjson_editions"],
        dependencies=[Depends(inject_session_into_request)],
    )

    @router.get(
        "",
        response_model=list[MtgjsonEdition],
        operation_id="list_editions",
        summary="Search for editions (sets)",
    )
    async def list_editions(
        request: Request,
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
    ) -> list[MtgjsonEdition]:
        query = EditionsQuery(set_code=set_code, name=name)
        query = validator.validate_edition_query(query)
        session = get_request_session(request)
        editions = await service.query_editions(session, query)
        return list(editions)

    @router.get(
        "/{set_code}",
        response_model=MtgjsonEdition,
        operation_id="get_edition",
        summary="Get one edition by set code.",
    )
    async def get_edition_by_set_code(
        set_code: str,
        request: Request,
    ) -> MtgjsonEdition:
        session = get_request_session(request)
        edition = await service.get_edition(session, set_code)
        if edition is None:
            raise HTTPException(status_code=404, detail="Edition not found")
        return edition

    return router
