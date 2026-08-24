"""
Shared pytest fixtures.

Day 1 tests intentionally avoid requiring a live PostgreSQL instance so
they can run in CI / any developer machine without extra setup. Database
*configuration* is still exercised directly (see test_database.py).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """A FastAPI test client for the application."""
    return TestClient(app)
