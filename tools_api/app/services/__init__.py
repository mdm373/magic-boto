"""Services layer for tool endpoints."""

from .batch_client import ApiBatchStatus, BatchApiClient, Request, create_batch_client
from .batch_poll import BatchPoller, BatchPollProvider, create_batch_poller
from .batch_verdict import Verdict
from .card_payload import card_to_dict, cards_to_csv, cards_to_csv_with_names
from .card_search_query_builder import CardSearchQueryBuilder
from .card_service import CardService
from .edition_service import EditionService
from .edition_validator import EditionQueryValidator
from .inventory_csv_parser import CsvInventoryRow, CsvParser
from .inventory_merger import CsvInventoryRowMerger
from .inventory_names import DEFAULT_INVENTORY_NAME
from .inventory_service import InventoryService
from .mapper import CardMapper, EditionMapper
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


__all__ = [
    "ApiBatchStatus",
    "BatchApiClient",
    "BatchPoller",
    "BatchPollProvider",
    "CardMapper",
    "CardSearchQueryBuilder",
    "CardService",
    "CsvInventoryRow",
    "CsvInventoryRowMerger",
    "CsvParser",
    "DEFAULT_INVENTORY_NAME",
    "EditionMapper",
    "EditionQueryValidator",
    "EditionService",
    "InventoryService",
    "Request",
    "TagService",
    "Verdict",
    "card_to_dict",
    "cards_to_csv",
    "cards_to_csv_with_names",
    "create_batch_client",
    "create_batch_poller",
    "create_card_service",
    "create_edition_service",
    "create_inventory_service",
    "create_tag_service",
]
