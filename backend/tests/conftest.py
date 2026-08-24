"""
Shared pytest fixtures.

Provides test client and isolated database session fixtures for unit tests
without requiring a running PostgreSQL instance or external services.
"""

from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """A FastAPI test client for the application."""
    return TestClient(app)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """
    An isolated in-memory SQLite database session with enforced foreign keys
    for testing models, relationships, and constraints.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
