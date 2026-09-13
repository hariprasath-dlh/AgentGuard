"""Phase 15: Security Hardening & Attack Simulation Test Suite.

Validates core security invariants of AgentGuard:
1. Authentication & JWT security (tampered tokens, expired tokens, missing headers)
2. RBAC enforcement (endpoint gating according to project matrix)
3. Multi-tenant Org isolation (cross-tenant access prevention)
4. Input validation & injection protection (SQLi, XSS, payload limits)
5. Audit Vault cryptographic chain immutability
6. CRITICAL risk tool bypass immunity (permission override guarantee)
"""
import os
import uuid
import time
import pytest
import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.core.config import settings
from app.security.jwt import create_access_token
from app.security.password import hash_password
from app.models.organization import Organization
from app.models.user import User
from app.models.agent import Agent
from app.models.tool import Tool
from app.models.permission import AgentToolPermission
from app.models.audit_log import AuditLog
from app.models.tool_request import ToolRequest
from app.models.hitl_request import HITLRequest
from app.schemas.policy import DecisionInput, CallerIdentity
from app.services.audit_vault import record_audit_log, verify_organization_chain
from app.services.factory import create_policy_engine
from app.services.policy_engine import PolicyEngine, default_budget_checker, default_rate_limit_checker
from tests.conftest import register_user, login_user, auth_headers


@pytest.fixture
def security_setup(client: TestClient, db_session: Session):
    """Sets up Org Alpha (with Admin, Dev, Security users) and Org Beta (with Admin)."""
    # Register Admin Alpha (creates Org Alpha)
    res_admin, slug_a = register_user(client, "admin@alpha.com", "Password123!", role="ADMIN")
    assert res_admin.status_code == 201, f"Reg Admin failed: {res_admin.text}"
    token_admin_a = login_user(client, "admin@alpha.com", "Password123!", slug_a).json()["access_token"]
    
    # Register Dev Alpha in Org Alpha
    res_dev, _ = register_user(client, "dev@alpha.com", "Password123!", slug=slug_a, role="DEVELOPER")
    assert res_dev.status_code == 201, f"Reg Dev failed: {res_dev.text}"
    token_dev_a = login_user(client, "dev@alpha.com", "Password123!", slug_a).json()["access_token"]

    # Register Security Alpha in Org Alpha
    res_sec, _ = register_user(client, "sec@alpha.com", "Password123!", slug=slug_a, role="SECURITY")
    assert res_sec.status_code == 201, f"Reg Sec failed: {res_sec.text}"
    token_sec_a = login_user(client, "sec@alpha.com", "Password123!", slug_a).json()["access_token"]

    # Register Admin Beta (creates Org Beta)
    res_beta, slug_b = register_user(client, "admin@beta.com", "Password123!", role="ADMIN")
    assert res_beta.status_code == 201, f"Reg Admin Beta failed: {res_beta.text}"
    token_admin_b = login_user(client, "admin@beta.com", "Password123!", slug_b).json()["access_token"]

    # Get Org Alpha DB models
    org_a = db_session.query(Organization).filter_by(slug=slug_a).first()
    admin_a_user = db_session.query(User).filter_by(email="admin@alpha.com").first()

    # Create Agent and Tools for Org Alpha
    agent_a = Agent(id=uuid.uuid4(), organization_id=org_a.id, name="AlphaAgent", status="ACTIVE")
    tool_critical = Tool(id=uuid.uuid4(), organization_id=org_a.id, name="delete_database", risk_level="CRITICAL")
    tool_normal = Tool(id=uuid.uuid4(), organization_id=org_a.id, name="read_data", risk_level="LOW")
    db_session.add_all([agent_a, tool_critical, tool_normal])
    db_session.commit()

    return {
        "slug_a": slug_a,
        "slug_b": slug_b,
        "org_a": org_a,
        "admin_a_user": admin_a_user,
        "token_admin_a": token_admin_a,
        "token_dev_a": token_dev_a,
        "token_sec_a": token_sec_a,
        "token_admin_b": token_admin_b,
        "agent_a": agent_a,
        "tool_critical": tool_critical,
        "tool_normal": tool_normal
    }


class TestAuthenticationSecurity:
    """Tests JWT authentication tampering, expiration, and header validation."""

    def test_missing_auth_header_rejected(self, client: TestClient):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_tampered_jwt_signature_rejected(self, client: TestClient, security_setup):
        token = security_setup["token_admin_a"]
        tampered = token[:-4] + "XXXX"
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
        assert r.status_code == 401

    def test_expired_jwt_rejected(self, client: TestClient, security_setup):
        user_id = str(security_setup["admin_a_user"].id)
        payload = {
            "sub": user_id,
            "exp": int(time.time()) - 3600  # expired 1 hour ago
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert r.status_code == 401

    def test_malformed_auth_header_rejected(self, client: TestClient):
        r = client.get("/api/v1/auth/me", headers={"Authorization": "NotBearer invalid_token_here"})
        assert r.status_code == 401


class TestRBACSecurityEnforcement:
    """Tests that endpoints strictly enforce role permissions."""

    def test_developer_cannot_access_audit_logs(self, client: TestClient, security_setup):
        r = client.get("/api/v1/audit", headers=auth_headers(security_setup["token_dev_a"]))
        assert r.status_code == 403

    def test_security_role_cannot_approve_hitl(self, client: TestClient, db_session: Session, security_setup):
        # Create a pending ToolRequest & HITLRequest
        tr = ToolRequest(
            id=uuid.uuid4(),
            organization_id=security_setup["org_a"].id,
            agent_id=security_setup["agent_a"].id,
            tool_id=security_setup["tool_normal"].id,
            input_payload={"customer_id": "C123"},
            decision="PENDING",
        )
        db_session.add(tr)
        db_session.flush()

        hitl = HITLRequest(
            id=uuid.uuid4(),
            organization_id=security_setup["org_a"].id,
            tool_request_id=tr.id,
            status="PENDING",
        )
        db_session.add(hitl)
        db_session.commit()

        r = client.post(
            f"/api/v1/hitl/{hitl.id}/approve",
            json={"reason": "security override attempt"},
            headers=auth_headers(security_setup["token_sec_a"])
        )
        assert r.status_code == 403

    def test_admin_can_approve_hitl(self, client: TestClient, db_session: Session, security_setup):
        tr = ToolRequest(
            id=uuid.uuid4(),
            organization_id=security_setup["org_a"].id,
            agent_id=security_setup["agent_a"].id,
            tool_id=security_setup["tool_normal"].id,
            input_payload={"customer_id": "C123"},
            decision="PENDING",
        )
        db_session.add(tr)
        db_session.flush()

        hitl = HITLRequest(
            id=uuid.uuid4(),
            organization_id=security_setup["org_a"].id,
            tool_request_id=tr.id,
            status="PENDING",
        )
        db_session.add(hitl)
        db_session.commit()

        r = client.post(
            f"/api/v1/hitl/{hitl.id}/approve",
            json={"reason": "Admin approved"},
            headers=auth_headers(security_setup["token_admin_a"])
        )
        assert r.status_code == 200


class TestTenantIsolation:
    """Tests multi-tenant boundary enforcement (Org A cannot reach Org B data)."""

    def test_cross_org_agent_access_denied(self, client: TestClient, security_setup):
        agent_a_id = str(security_setup["agent_a"].id)
        # Admin B tries to access Org A's agent
        r = client.get(f"/api/v1/agents/{agent_a_id}", headers=auth_headers(security_setup["token_admin_b"]))
        assert r.status_code in (403, 404)


class TestInputValidationAndInjection:
    """Tests payload boundaries and SQLi/XSS resilience."""

    def test_invalid_uuid_route_param(self, client: TestClient, security_setup):
        r = client.get("/api/v1/agents/not-a-valid-uuid", headers=auth_headers(security_setup["token_admin_a"]))
        assert r.status_code == 422  # Pydantic validation error

    def test_sql_injection_attempt_in_login(self, client: TestClient):
        r = client.post("/api/v1/auth/login", json={
            "email": "admin@alpha.com' OR '1'='1",
            "password": "wrongpassword"
        })
        assert r.status_code in (401, 422)


class TestAuditChainImmutability:
    """Tests cryptographic chain verification."""

    def test_genesis_and_subsequent_hash_chain(self, db_session: Session, security_setup):
        org_id = security_setup["org_a"].id
        
        entry1 = record_audit_log(
            db=db_session,
            organization_id=org_id,
            agent_id=None,
            tool_id=None,
            event_type="TEST_1",
            decision="ALLOW",
            payload={"step": 1},
            request_id=uuid.uuid4(),
            tool_name="test_tool"
        )
        
        entry2 = record_audit_log(
            db=db_session,
            organization_id=org_id,
            agent_id=None,
            tool_id=None,
            event_type="TEST_2",
            decision="ALLOW",
            payload={"step": 2},
            request_id=uuid.uuid4(),
            tool_name="test_tool"
        )
        
        assert entry1.previous_hash == "0" * 64
        assert entry2.previous_hash == entry1.current_hash
        assert len(entry2.current_hash) == 64
        
        # Verify chain integrity function
        result = verify_organization_chain(db_session, org_id)
        assert result["status"] == "VALID"
        assert result["total_records"] >= 2


class TestCriticalRiskOverrideGuarantee:
    """Tests that CRITICAL risk level tools are ALWAYS DENIED even if explicitly permitted."""

    def test_critical_tool_denied_with_explicit_permission(self, db_session: Session, security_setup):
        agent = security_setup["agent_a"]
        critical_tool = security_setup["tool_critical"]
        
        # Grant explicit permission is_allowed=True
        perm = AgentToolPermission(
            id=uuid.uuid4(),
            organization_id=security_setup["org_a"].id,
            agent_id=agent.id,
            tool_id=critical_tool.id,
            is_allowed=True
        )
        db_session.add(perm)
        db_session.commit()

        # Instantiate policy engine directly with stub checkers
        engine = PolicyEngine(
            db=db_session,
            budget_checker=default_budget_checker,
            rate_limit_checker=default_rate_limit_checker
        )

        input_data = DecisionInput(
            agent_id=agent.id,
            tool_name="delete_database",
            action="delete",
            parameters={"target": "production"},
        )
        caller = CallerIdentity(
            organization_id=security_setup["org_a"].id,
            caller_id=agent.id,
            role="ADMIN",
        )

        decision = engine.evaluate(input_data=input_data, caller=caller)

        assert decision.decision.value == "DENY"
        assert "CRITICAL" in decision.reason.upper()
