"""MTGJSON-compatible API namespace."""

from fastapi import APIRouter

from app.validators import CardQueryValidator, EditionQueryValidator

from .card_router import create_card_router
from .edition_router import create_edition_router

mtgjson_router = APIRouter(prefix="/mtgjson")
mtgjson_router.include_router(create_card_router(CardQueryValidator()))
mtgjson_router.include_router(create_edition_router(EditionQueryValidator()))

__all__ = ["mtgjson_router"]
