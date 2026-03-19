"""Services layer for tool endpoints."""

from app.services.card_service import CardService
from app.services.edition_service import EditionService
from app.services.mapper import CardMapper, EditionMapper


def create_card_service() -> CardService:
    """Create the card service with its mapper dependency."""
    return CardService(CardMapper())


def create_edition_service() -> EditionService:
    """Create the edition service with its mapper dependency."""
    return EditionService(EditionMapper())


__all__ = ["create_card_service", "create_edition_service", "CardService", "EditionService"]
