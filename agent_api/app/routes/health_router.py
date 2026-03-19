from fastapi import APIRouter

health_router = APIRouter(tags=["health"])


@health_router.get("/")
def health() -> dict[str, str]:
    """Healthcheck."""
    return {"status": "ok"}
