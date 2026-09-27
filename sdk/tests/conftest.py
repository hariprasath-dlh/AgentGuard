"""Pytest fixtures for AgentGuard SDK testing against live backend.

Spins up the actual FastAPI application via uvicorn on a background thread,
communicating over real TCP sockets to test real HTTP behavior, real network
timeouts, and real database records in PostgreSQL.
"""
import os

TEST_DB_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DB_URL:
    raise RuntimeError(
        "SDK tests require TEST_DATABASE_URL to be explicitly set to a PostgreSQL database. "
        "Example: TEST_DATABASE_URL=postgresql://agentguard:agentguard_password@localhost:5432/agentguard"
    )
if TEST_DB_URL.startswith("sqlite"):
    raise RuntimeError(
        "SDK tests must run against PostgreSQL, not SQLite. "
        "Set TEST_DATABASE_URL=postgresql://agentguard:agentguard_password@localhost:5432/agentguard"
    )

os.environ["DATABASE_URL"] = TEST_DB_URL

import threading
import time
import uuid
from typing import Generator

import httpx
import pytest
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
settings.DATABASE_URL = TEST_DB_URL

import app.core.database as db_module
db_module.engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_module.engine)

from app.core.database import Base
from app.core.seed import seed
from app.main import app as backend_app
from app.models.agent import Agent
from app.models.api_key import APIKey
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.security.api_key import generate_api_key

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
    test_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
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
def test_env(db_session: Session, live_backend_server: str) -> Generator[dict, None, None]:
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

    try:
        yield {
            "org": org,
            "agent": agent,
            "api_key": raw_key,
            "base_url": live_backend_server,
            "org_id": org.id,
            "agent_id": agent.id,
        }
    finally:
        from app.models.hitl_request import HITLRequest
        from app.models.tool_request import ToolRequest
        from app.models.audit_log import AuditLog
        from app.models.budget import Budget
        from app.models.role import Role
        from app.models.user import User

        try:
            db_session.query(HITLRequest).filter(HITLRequest.organization_id == org.id).delete()
            db_session.query(ToolRequest).filter(ToolRequest.organization_id == org.id).delete()
            db_session.query(AuditLog).filter(AuditLog.organization_id == org.id).delete()
            db_session.query(Budget).filter(Budget.organization_id == org.id).delete()
            db_session.query(AgentToolPermission).filter(AgentToolPermission.organization_id == org.id).delete()
            db_session.query(APIKey).filter(APIKey.organization_id == org.id).delete()
            db_session.query(Agent).filter(Agent.organization_id == org.id).delete()
            db_session.query(Tool).filter(Tool.organization_id == org.id).delete()
            db_session.query(User).filter(User.organization_id == org.id).delete()
            db_session.query(Role).filter(Role.organization_id == org.id).delete()
            db_session.delete(org)
            db_session.commit()
        except Exception:
            db_session.rollback()
