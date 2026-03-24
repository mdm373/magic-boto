"""Pydantic response/request schemas."""

from .card_schema import (
    CardsListMetadata,
    CardsListResponse,
    CardsPage,
    CardsPaginationParams,
    MtgjsonCard,
)
from .card_search import CardSearchFilters, CardSearchPagination, CardSearchQuery
from .descriptions import allowed_values_description
from .edition_schema import EditionsQuery, MtgjsonEdition
from .inventory_schema import (
    AddInventoryCardsBody,
    AddInventoryCardsRequest,
    CreateInventoryRequest,
    InventoryResponse,
    build_add_inventory_cards_request,
)

__all__ = [
    "allowed_values_description",
    "CardSearchFilters",
    "CardSearchPagination",
    "CardSearchQuery",
    "CardsListMetadata",
    "CardsListResponse",
    "CardsPage",
    "CardsPaginationParams",
    "EditionsQuery",
    "MtgjsonCard",
    "MtgjsonEdition",
    "AddInventoryCardsBody",
    "AddInventoryCardsRequest",
    "CreateInventoryRequest",
    "InventoryResponse",
    "build_add_inventory_cards_request",
]
