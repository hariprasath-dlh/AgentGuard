"""Pytest fixtures for AgentGuard SDK testing against live backend.

Spins up the actual FastAPI application via uvicorn on a background thread,
communicating over real TCP sockets to test real HTTP behavior, real network
timeouts, and real database records in PostgreSQL.
"""
import os
import threading
import time
import uuid
from typing import Generator

import httpx
import pytest
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.seed import seed
from app.main import app as backend_app
from app.models.agent import Agent
from app.models.api_key import APIKey
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.security.api_key import generate_api_key

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://agentguard:agentguard_password@localhost:5432/agentguard"),
)
TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_PORT = 8088
TEST_BASE_URL = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}/api/v1"


class UvicornTestServer(uvicorn.Server):
    """Custom uvicorn server running in a background thread for testing."""
    def install_signal_handlers(self):
        pass


@pytest.fixture(scope="session", autouse=True)
def live_backend_server() -> Generator[str, None, None]:
    """Start the actual FastAPI app on a real TCP port for the entire test session."""
    config = uvicorn.Config(
        app=backend_app,
        host=TEST_SERVER_HOST,
        port=TEST_SERVER_PORT,
        log_level="error",
    )
    server = UvicornTestServer(config=config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to become ready
    health_url = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}/health"
    ready = False
    for _ in range(50):
        try:
            r = httpx.get(health_url, timeout=0.5)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.1)

    if not ready:
        raise RuntimeError(f"Could not connect to live backend test server at {health_url}")

    yield TEST_BASE_URL

    server.should_exit = True
    thread.join(timeout=2.0)


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=test_engine)
    return test_engine


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    """Provide a real PostgreSQL database session for setup and verification."""
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_env(db_session: Session, live_backend_server: str) -> dict:
    """Set up test organization, agent, active API key, and seeded demo tools."""
    org_slug = f"sdk-org-{uuid.uuid4().hex[:6]}"
    org = Organization(name="SDK Test Org", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    # Seed demo tools (read_customer, create_ticket, send_email, process_refund, delete_database)
    seed(db_session, org_slug=org_slug)

    agent = Agent(
        organization_id=org.id,
        name="SDKTestAgent",
        description="Autonomous Agent for SDK Validation",
        status="ACTIVE",
    )
    db_session.add(agent)
    db_session.flush()

    raw_key, key_prefix, key_hash = generate_api_key(prefix="ag_agent")
    api_key = APIKey(
        organization_id=org.id,
        agent_id=agent.id,
        name="SDKAgentKey",
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
    )
    db_session.add(api_key)

    # Grant permissions for tools
    for tool_name in ("read_customer", "process_refund", "delete_database"):
        tool = (
            db_session.query(Tool)
            .filter(Tool.organization_id == org.id, Tool.name == tool_name)
            .first()
        )
        if tool:
            perm = AgentToolPermission(
                agent_id=agent.id,
                tool_id=tool.id,
                organization_id=org.id,
                is_allowed=True,
            )
            db_session.add(perm)

    db_session.commit()

    return {
        "org": org,
        "agent": agent,
        "api_key": raw_key,
        "base_url": live_backend_server,
        "org_id": org.id,
        "agent_id": agent.id,
    }
