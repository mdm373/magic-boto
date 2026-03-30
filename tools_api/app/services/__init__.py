"""Services layer for tool endpoints."""

from .card_search_query_builder import CardSearchQueryBuilder
from .card_service import CardService
from .edition_service import EditionService
from .inventory_service import InventoryService
from .mapper import CardMapper, EditionMapper
from .oracle_tag_sweep_service import OracleTagSweepService
from .tag_service import TagService


def create_card_service() -> CardService:
    """Create the card service with mapper and card search query builder."""
    return CardService(CardMapper(), CardSearchQueryBuilder())


def create_edition_service() -> EditionService:
    """Create the edition service with its mapper dependency."""
    return EditionService(EditionMapper())


def create_inventory_service() -> InventoryService:
    """Create the inventory service."""
    return InventoryService()


def create_tag_service() -> TagService:
    """Create the tag service."""
    return TagService()


def create_oracle_tag_sweep_service() -> OracleTagSweepService:
    """Create the oracle tag sweep service."""
    return OracleTagSweepService()


__all__ = [
    "create_card_service",
    "create_edition_service",
    "create_inventory_service",
    "create_tag_service",
    "create_oracle_tag_sweep_service",
    "CardSearchQueryBuilder",
    "CardService",
    "EditionService",
    "InventoryService",
    "TagService",
    "OracleTagSweepService",
]
