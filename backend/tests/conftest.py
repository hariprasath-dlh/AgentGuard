"""Pytest configuration for Phase 3 auth tests.

Uses SQLite in-memory by default (fast, no external deps).
Set TEST_DATABASE_URL env var to a real postgres URL for accurate dialect testing.

The key threading fix: SQLite connections must be created with
check_same_thread=False because FastAPI's TestClient runs endpoints in
worker threads (via anyio), while the session is created on the main thread.
"""
import os
import uuid
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app


# ---------------------------------------------------------------------------
# SQLite FK enforcement (no-op for non-SQLite; safe to run always)
# ---------------------------------------------------------------------------
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Engine fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def engine():
    url = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    # check_same_thread=False is required: FastAPI TestClient runs route
    # handlers in worker threads, but the in-memory SQLite connection is
    # created in the main test thread.
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    test_engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


# ---------------------------------------------------------------------------
# Per-test session with transaction rollback for isolation
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def db_session(engine):
    """Wraps each test in a savepoint so the DB state rolls back after."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, expire_on_commit=False)
    session = Session()
    # For SQLite we need nested transactions via savepoints to allow the
    # session.begin_nested() calls inside the app to work correctly.
    try:
        session.begin_nested()
    except Exception:
        pass  # Postgres doesn't need this workaround
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient with DB override
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Reusable helpers
# ---------------------------------------------------------------------------
def make_unique_slug():
    return f"org-{uuid.uuid4().hex[:8]}"


def register_user(client, email, password="Password1!", slug=None, role=None):
    slug = slug or make_unique_slug()
    payload = {
        "email": email,
        "password": password,
        "organization_slug": slug,
    }
    if role:
        payload["role"] = role
    resp = client.post("/api/v1/auth/register", json=payload)
    return resp, slug


def login_user(client, email, password="Password1!", slug=None):
    payload = {"email": email, "password": password}
    if slug:
        payload["organization_slug"] = slug
    return client.post("/api/v1/auth/login", json=payload)


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
