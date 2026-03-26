"""API route modules."""

from fastapi import APIRouter

from app.validators import EditionQueryValidator

from .card_router import create_card_router
from .edition_router import create_edition_router
from .inventory_router import create_inventory_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(create_card_router())
v1_router.include_router(create_edition_router(EditionQueryValidator()))
v1_router.include_router(create_inventory_router())

__all__ = ["v1_router"]
