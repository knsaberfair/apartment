import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_DB = ROOT / "test_app.db"
os.environ["APARTMENT_ENV"] = "test"
os.environ["APARTMENT_DB_PATH"] = str(TEST_DB)

from app.database import get_connection, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    if TEST_DB.exists():
        TEST_DB.unlink()
    init_db()
    with get_connection() as db:
        seed_if_empty(db)
    yield
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    assert client.cookies.get("apartment_auth")
    return response.json()["access_token"]


@pytest.fixture
def viewer_token(client):
    response = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert response.status_code == 200
    assert client.cookies.get("apartment_auth")
    return response.json()["access_token"]
