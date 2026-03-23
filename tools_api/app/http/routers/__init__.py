"""API route modules."""

from fastapi import APIRouter

from .inventory_router import create_inventory_router
from .mtgjson import mtgjson_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(mtgjson_router)
v1_router.include_router(create_inventory_router())

__all__ = ["v1_router"]
