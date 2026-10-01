"""Framework-neutral page container returned by paginating repository methods."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """One page of rows plus the total count of rows matching the query.

    Deliberately *not* an HTTP pagination type. Keeping ``fastapi_pagination`` out of the
    repository and service layers means a Celery worker that only inserts cards no longer
    imports FastAPI transitively. The HTTP route and MCP tool adapt this into ``CardsPage``
    at the edge via ``app.api_schema.card_page.to_cards_page``.
    """

    items: Sequence[T]
    total: int
    page_number: int
    page_size: int
