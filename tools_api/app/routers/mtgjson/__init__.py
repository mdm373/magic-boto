"""MTGJSON-compatible API namespace."""

from fastapi import APIRouter

from .cards import cards_router

mtgjson_router = APIRouter(prefix="/mtgjson")
mtgjson_router.include_router(cards_router)

__all__ = ["mtgjson_router"]
