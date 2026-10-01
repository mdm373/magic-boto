"""HTTP/MCP pagination envelope for card search results.

Split out of ``card_schema`` and deliberately **not** re-exported from the ``app.api_schema``
barrel: this is the only module in the package that imports ``fastapi_pagination``. Keeping it
off the barrel means importing a domain schema (e.g. ``Tag`` from ``tag_schema``) no longer
drags FastAPI into processes that serve no HTTP -- notably the Celery worker. The two callers
are the HTTP route and the MCP tool, both of which import this module directly.
"""

from __future__ import annotations

from fastapi import Query
from fastapi_pagination import Page, Params
from fastapi_pagination.customization import CustomizedPage, UseParams
from pydantic import field_validator

from app.api_schema.card_pagination_limits import CARD_CATALOG_MAX_PAGE_SIZE
from app.api_schema.card_schema import Card
from app.repository.page import Page as RepositoryPage


class CardsPaginationParams(Params):
    """Pagination params for cards endpoints."""

    size: int = Query(
        default=100,
        ge=1,
        description=f"Page size; values above {CARD_CATALOG_MAX_PAGE_SIZE} are capped.",
    )

    @field_validator("size", mode="after")
    @classmethod
    def _clamp_size(cls, value: int) -> int:
        if value > CARD_CATALOG_MAX_PAGE_SIZE:
            return CARD_CATALOG_MAX_PAGE_SIZE
        return value


CardsPage = CustomizedPage[Page[Card], UseParams(CardsPaginationParams)]


def to_cards_page(page: RepositoryPage[Card]) -> CardsPage:
    """Adapt a service-layer page into the ``CardsPage`` wire shape.

    The only place ``fastapi_pagination`` meets a repository/service result -- both the HTTP
    route and the MCP tool go through here so the serialized shape stays identical.
    """
    return CardsPage.create(
        list(page.items),
        CardsPaginationParams(page=page.page_number, size=page.page_size),
        total=page.total,
    )


__all__ = ["CardsPage", "CardsPaginationParams", "to_cards_page"]
