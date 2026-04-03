"""Services layer for tool endpoints."""

from .batch_poll import BatchPoller, BatchPollProvider, create_batch_poller
from .batch_service import BatchService
from .card_search_query_builder import CardSearchQueryBuilder
from .card_service import CardService
from .edition_service import EditionService
from .inventory_service import InventoryService
from .mapper import CardMapper, EditionMapper
from .sweep_run_service import BatchChunkRecord, TagSweepService
from .tag_audit_service import TagAuditService
from .tag_service import TagService


def create_batch_service() -> BatchService:
    """Create the batch service."""
    return BatchService()


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


def create_tag_sweep_service() -> TagSweepService:
    """Create the tag sweep service."""
    return TagSweepService()


def create_tag_audit_service() -> TagAuditService:
    """Create the tag audit service."""
    return TagAuditService()


__all__ = [
    "create_batch_service",
    "create_card_service",
    "create_edition_service",
    "create_inventory_service",
    "create_tag_service",
    "create_tag_sweep_service",
    "create_tag_audit_service",
    "BatchChunkRecord",
    "BatchPollProvider",
    "BatchPoller",
    "create_batch_poller",
    "BatchService",
    "CardSearchQueryBuilder",
    "CardService",
    "EditionService",
    "InventoryService",
    "TagAuditService",
    "TagService",
    "TagSweepService",
]
