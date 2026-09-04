import os
import tempfile
import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from app.models import (
    Agent,
    AgentToolPermission,
    APIKey,
    AuditLog,
    Budget,
    HITLRequest,
    Organization,
    Policy,
    Role,
    Tool,
    ToolRequest,
    User,
)


def test_alembic_migration_on_empty_db():
    """Test that alembic upgrade head applies cleanly on an empty database."""
    fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = None

    try:
        db_url = f"sqlite:///{tmp_db_path}"
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")

        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))

        # Run migration upgrade to head
        command.upgrade(alembic_cfg, "head")

        # Verify all 12 tables exist in the migrated database
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "organizations",
            "roles",
            "users",
            "api_keys",
            "agents",
            "tools",
            "agent_tool_permissions",
            "policies",
            "budgets",
            "audit_logs",
            "tool_requests",
            "hitl_requests",
            "alembic_version",
        }
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"
    finally:
        if engine is not None:
            engine.dispose()
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except Exception:
                pass


def test_organization_creation(db_session):
    """Test creating an organization."""
    org = Organization(name="Acme Corp", slug="acme-corp")
    db_session.add(org)
    db_session.commit()

    assert org.id is not None
    assert org.created_at is not None
    assert org.updated_at is not None


def test_foreign_key_enforcement_missing_parent(db_session):
    """Test that foreign key constraint rejects non-existent parent."""
    non_existent_org_id = uuid.uuid4()

    agent = Agent(
        organization_id=non_existent_org_id,
        name="SecurityAgent",
        description="Handles security scans",
    )
    db_session.add(agent)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tool_request_foreign_key_enforcement(db_session):
    """Test creating a tool_request with non-existent agent_id fails."""
    org = Organization(name="Test Org", slug="test-org-fk")
    db_session.add(org)
    db_session.commit()

    tool = Tool(organization_id=org.id, name="query_db", risk_level="LOW")
    db_session.add(tool)
    db_session.commit()

    non_existent_agent_id = uuid.uuid4()
    req = ToolRequest(
        organization_id=org.id,
        agent_id=non_existent_agent_id,
        tool_id=tool.id,
        decision="ALLOW",
    )
    db_session.add(req)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_hitl_request_foreign_key_enforcement(db_session):
    """Test creating a hitl_request with non-existent tool_request_id fails."""
    org = Organization(name="HITL Org", slug="hitl-org")
    db_session.add(org)
    db_session.commit()

    non_existent_tool_req_id = uuid.uuid4()
    hitl = HITLRequest(
        organization_id=org.id,
        tool_request_id=non_existent_tool_req_id,
        status="PENDING",
    )
    db_session.add(hitl)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_constraint_org_slug(db_session):
    """Test unique constraint on organizations.slug."""
    org1 = Organization(name="Org 1", slug="duplicate-slug")
    org2 = Organization(name="Org 2", slug="duplicate-slug")
    db_session.add(org1)
    db_session.commit()

    db_session.add(org2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_constraint_user_email_per_org(db_session):
    """Test unique constraint on user email per organization."""
    org1_id = uuid.uuid4()
    org1 = Organization(id=org1_id, name="Org 1", slug="org-1-email")
    db_session.add(org1)
    db_session.commit()

    user1 = User(
        organization_id=org1_id,
        email="alice@example.com",
        hashed_password="hashed_pw_1",
    )
    db_session.add(user1)
    db_session.commit()

    # Same email in same org -> fails
    user2 = User(
        organization_id=org1_id,
        email="alice@example.com",
        hashed_password="hashed_pw_2",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Same email in different org -> succeeds
    org2_id = uuid.uuid4()
    org2 = Organization(id=org2_id, name="Org 2", slug="org-2-email")
    db_session.add(org2)
    db_session.commit()

    user3 = User(
        organization_id=org2_id,
        email="alice@example.com",
        hashed_password="hashed_pw_3",
    )
    db_session.add(user3)
    db_session.commit()
    assert user3.id is not None


def test_unique_constraint_api_key_hash(db_session):
    """Test unique constraint on api_keys.key_hash."""
    org = Organization(name="Org API", slug="org-api")
    db_session.add(org)
    db_session.commit()

    k1 = APIKey(
        organization_id=org.id,
        key_hash="hash_12345",
        key_prefix="ag_live",
        name="Key 1",
    )
    k2 = APIKey(
        organization_id=org.id,
        key_hash="hash_12345",
        key_prefix="ag_live",
        name="Key 2",
    )
    db_session.add(k1)
    db_session.commit()

    db_session.add(k2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_constraint_agent_tool_permission(db_session):
    """Test unique constraint on agent_tool_permissions (agent_id, tool_id)."""
    org = Organization(name="Org Perm", slug="org-perm")
    db_session.add(org)
    db_session.commit()

    agent = Agent(organization_id=org.id, name="FinanceAgent")
    tool = Tool(organization_id=org.id, name="refund_tool", risk_level="HIGH")
    db_session.add_all([agent, tool])
    db_session.commit()

    perm1 = AgentToolPermission(
        organization_id=org.id, agent_id=agent.id, tool_id=tool.id, is_allowed=True
    )
    perm2 = AgentToolPermission(
        organization_id=org.id, agent_id=agent.id, tool_id=tool.id, is_allowed=False
    )
    db_session.add(perm1)
    db_session.commit()

    db_session.add(perm2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_constraint_agent_budget(db_session):
    """Test 1-to-1 budget constraint per agent."""
    org = Organization(name="Org Budget", slug="org-budget")
    db_session.add(org)
    db_session.commit()

    agent = Agent(organization_id=org.id, name="BudgetAgent")
    db_session.add(agent)
    db_session.commit()

    b1 = Budget(organization_id=org.id, agent_id=agent.id, max_budget_per_day=Decimal("100.00"))
    b2 = Budget(organization_id=org.id, agent_id=agent.id, max_budget_per_day=Decimal("200.00"))
    db_session.add(b1)
    db_session.commit()

    db_session.add(b2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_not_null_constraints(db_session):
    """Test NOT NULL constraints reject missing required fields."""
    # Organization without name
    org = Organization(name=None, slug="no-name-org")
    db_session.add(org)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Tool without name
    valid_org = Organization(name="Valid Org", slug="valid-org")
    db_session.add(valid_org)
    db_session.commit()

    tool = Tool(organization_id=valid_org.id, name=None, risk_level="LOW")
    db_session.add(tool)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # AuditLog without event_type
    audit = AuditLog(
        organization_id=valid_org.id,
        event_type=None,
        current_hash="hash_value",
    )
    db_session.add(audit)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_all_12_tables_relationship_chain(db_session):
    """Test creating instances across all 12 tables and verifying their relations."""
    org = Organization(name="Full Flow Org", slug="full-flow-org")
    db_session.add(org)
    db_session.commit()

    role = Role(organization_id=org.id, name="ADMIN", description="Administrator")
    db_session.add(role)
    db_session.commit()

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="admin@fullflow.com",
        hashed_password="pw_hash_test",
        full_name="Admin User",
    )
    db_session.add(user)
    db_session.commit()

    agent = Agent(
        organization_id=org.id,
        name="FinanceAgent",
        description="Autonomous Finance Agent",
        status="ACTIVE",
    )
    tool = Tool(
        organization_id=org.id,
        name="process_refund",
        description="Processes customer refund",
        risk_level="CRITICAL",
    )
    policy = Policy(
        organization_id=org.id,
        name="HighRiskRefundPolicy",
        policy_type="RISK",
        rules={"action": "REQUIRE_HITL", "max_amount": 500},
    )
    db_session.add_all([agent, tool, policy])
    db_session.commit()

    permission = AgentToolPermission(
        organization_id=org.id,
        agent_id=agent.id,
        tool_id=tool.id,
        is_allowed=True,
    )
    budget = Budget(
        organization_id=org.id,
        agent_id=agent.id,
        max_requests_per_minute=60,
        max_requests_per_day=1000,
        max_budget_per_day=Decimal("50.00"),
    )
    api_key = APIKey(
        organization_id=org.id,
        agent_id=agent.id,
        key_hash="hash_chain_demo_key",
        key_prefix="ag_test",
        name="Agent Key",
    )
    audit = AuditLog(
        organization_id=org.id,
        agent_id=agent.id,
        tool_id=tool.id,
        event_type="TOOL_REQUEST_EVALUATED",
        decision="PENDING",
        payload={"amount": 1000},
        previous_hash="0" * 64,
        current_hash="a" * 64,
        sequence_number=1,
    )
    db_session.add_all([permission, budget, api_key, audit])
    db_session.commit()

    tool_req = ToolRequest(
        organization_id=org.id,
        agent_id=agent.id,
        tool_id=tool.id,
        policy_id=policy.id,
        audit_log_id=audit.id,
        decision="PENDING",
        reason="Exceeds auto-approval limit, requires HITL approval",
        input_payload={"amount": 1000},
    )
    db_session.add(tool_req)
    db_session.commit()

    hitl = HITLRequest(
        organization_id=org.id,
        tool_request_id=tool_req.id,
        status="PENDING",
        reviewer_id=user.id,
    )
    db_session.add(hitl)
    db_session.commit()

    # Assert relations
    assert org.users[0].email == "admin@fullflow.com"
    assert org.agents[0].name == "FinanceAgent"
    assert org.tools[0].name == "process_refund"
    assert org.policies[0].name == "HighRiskRefundPolicy"
    assert agent.budget.max_requests_per_minute == 60
    assert agent.permissions[0].tool.name == "process_refund"
    assert tool_req.agent.name == "FinanceAgent"
    assert tool_req.hitl_request.status == "PENDING"
    assert hitl.reviewer.email == "admin@fullflow.com"
    assert hitl.tool_request.decision == "PENDING"
