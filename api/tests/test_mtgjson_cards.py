"""Integration tests for MTGJSON v1 cards API.

Requires DB up with MTGJSON data and POSTGRES_* in env (e.g. .env at repo root).
"""

from collections.abc import Generator

import pytest
from app.main import app
from fastapi.testclient import TestClient

SCRYFALL_ID_DARK_RITUAL = "4ebcd681-1871-4914-bcd7-6bd95829f6e0"
EXPECTED_DARK_RITUAL = {
    "name": "Dark Ritual",
    "mana_cost": "{B}",
    "set_code": "ICE",
    "scryfall_id": SCRYFALL_ID_DARK_RITUAL,
    "type": "Instant",
    "rarity": "common",
}


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI test client; lifespan runs for the duration of the with block."""
    with TestClient(app) as _app:
        yield _app


def test_get_card_by_scryfall_id_returns_expected(client: TestClient) -> None:
    """GET /mtgjson/v1/cards/{scryfall_id} returns the expected card payload."""
    response = client.get(f"/mtgjson/v1/cards/{SCRYFALL_ID_DARK_RITUAL}")
    assert response.status_code == 200
    data = response.json()
    assert data == EXPECTED_DARK_RITUAL
