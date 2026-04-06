"""API route modules."""

from fastapi import APIRouter

from app.services import EditionQueryValidator

from .card_router import create_card_image_router, create_card_router
from .edition_router import create_edition_router
from .tag_router import create_tag_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(create_card_router())
v1_router.include_router(create_card_image_router())
v1_router.include_router(create_edition_router(EditionQueryValidator()))
v1_router.include_router(create_tag_router())

__all__ = ["v1_router"]
