"""Pytest configuration for AgentGuard backend tests.

Uses SQLite in-memory by default (fast, no external deps).
Set TEST_DATABASE_URL env var to a real postgres URL for accurate dialect testing.

The key threading fix: SQLite connections must be created with
check_same_thread=False because FastAPI's TestClient runs endpoints in
worker threads (via anyio), while the session is created on the main thread.

Redis dependency: Tests that specifically test Redis behaviour (test_redis_guards,
test_runaway_agent) require a live Redis server and will skip automatically when
Redis is unavailable.  All other tests patch out Redis-backed checkers so they
run correctly without Redis.
"""
import os
import uuid
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# ── IMPORTANT: import all models BEFORE importing Base so that their
# ── __tablename__ declarations are registered on the shared Base.metadata.
import app.models  # noqa: F401 — registers all ORM models on Base
from app.core.database import Base, get_db
from app.main import app
from app.services.policy_engine import default_budget_checker, default_rate_limit_checker


# ---------------------------------------------------------------------------
# Redis availability probe (used to skip Redis-dependent tests)
# ---------------------------------------------------------------------------
def _redis_available() -> bool:
    try:
        import redis as _redis
        from app.core.redis import get_redis_client
        client = get_redis_client()
        client.ping()
        return True
    except Exception:
        return False


REDIS_AVAILABLE = _redis_available()
requires_redis = pytest.mark.skipif(
    not REDIS_AVAILABLE,
    reason="Redis server is not available; skipping Redis-dependent test"
)


# ---------------------------------------------------------------------------
# SQLite FK enforcement (no-op for non-SQLite; safe to run always)
# ---------------------------------------------------------------------------
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in type(dbapi_connection).__module__:
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
# FastAPI TestClient with DB override AND Redis-budget stub
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def client(db_session):
    """HTTP test client.

    * Overrides get_db with the isolated test session.
    * Patches create_policy_engine to use stub budget/rate-limit checkers
      so tests that don't test Redis don't fail when Redis is offline.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Patch the factory so PolicyEngine gets stub checkers (no Redis needed)
    from app.services.factory import create_policy_engine as _real_cpe
    from app.services.policy_engine import PolicyEngine

    def _stub_create_policy_engine(db, redis_client=None):
        return PolicyEngine(
            db=db,
            budget_checker=default_budget_checker,
            rate_limit_checker=default_rate_limit_checker,
        )

    with patch("app.api.guard.create_policy_engine", side_effect=_stub_create_policy_engine):
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
