"""Repository layer: pure ORM access organized by primary table concern."""

from .batch_repo import BatchRepo, BatchStatusMeta
from .canonical import canonical_name
from .card_keyword_repo import CardKeywordRepo
from .card_meta_repo import CardMetaRepo
from .card_repo import CardRepo
from .card_subtype_repo import CardSubtypeRepo
from .card_supertype_repo import CardSupertypeRepo
from .card_tag_repo import CardTagEntry, CardTagRepo
from .card_type_repo import CardTypeRepo
from .edition_repo import EditionRepo
from .inventory_repo import InventoryRepo
from .tag_audit_repo import TagAuditRepo
from .tag_repo import TagRepo, tag_from_model
from .tag_sweep_repo import BatchChunkRecord, TagSweepRepo

__all__ = [
    "BatchChunkRecord",
    "BatchStatusMeta",
    "canonical_name",
    "BatchRepo",
    "CardKeywordRepo",
    "CardMetaRepo",
    "CardRepo",
    "CardSubtypeRepo",
    "CardSupertypeRepo",
    "CardTagEntry",
    "CardTagRepo",
    "CardTypeRepo",
    "EditionRepo",
    "InventoryRepo",
    "TagAuditRepo",
    "TagRepo",
    "TagSweepRepo",
    "tag_from_model",
]
