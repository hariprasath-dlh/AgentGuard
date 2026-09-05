"""Comprehensive test suite for Phase 9: Human-in-the-Loop (HITL) Engine.

Tests cover:
  1. MANAGER can approve pending request and resume mock execution
  2. MANAGER can deny pending request; mock handler is never executed
  3. ADMIN can also approve and deny
  4. Forbidden roles (DEVELOPER, AUDITOR, SECURITY) receive 403
  5. Unauthenticated requests return 401
  6. Approving executes mock tool handler exactly once
  7. Approving/denying already-resolved request returns 400
  8. Approving an expired request is rejected as EXPIRED (400)
  9. sweep_expired_hitl_requests works in isolation
 10. Commit-before-execute ordering: approval stands even if mock handler raises
 11. Tool without registered mock handler records skipped_no_handler
 12. Audit chain remains unbroken through approve-then-execute cycle (verify_organization_chain)
 13. Full FinanceAgent refund demo scenario end-to-end
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.seed import seed
from app.main import app as fastapi_app
from app.models.agent import Agent
from app.models.api_key import APIKey
from app.models.audit_log import AuditLog
from app.models.hitl_request import HITLRequest
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.models.tool_request import ToolRequest
from app.models.user import User
from app.schemas.auth import RoleEnum
from app.security.api_key import generate_api_key
from app.services import mock_tools
from app.services.audit_vault import verify_organization_chain
from app.api.hitl import sweep_expired_hitl_requests


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------
def _http_client_for_session(session: Session) -> TestClient:
    def override_get_db():
        try:
            yield session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return TestClient(fastapi_app, raise_server_exceptions=True)


def _register_and_login(client: TestClient, org_slug: str, role: str = "MANAGER") -> dict:
    email = f"{uuid.uuid4().hex[:6]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password1!", "organization_slug": org_slug, "role": role},
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    r2 = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password1!", "organization_slug": org_slug},
    )
    assert r2.status_code == 200, f"Login failed: {r2.text}"
    token = r2.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def hitl_env(db_session: Session):
    """Set up org, demo tools, agent, API key, and manager user."""
    org_slug = f"hitl-org-{uuid.uuid4().hex[:6]}"
    org = Organization(name="HITL Test Org", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    # Seed demo tools (including process_refund)
    seed(db_session, org_slug=org_slug)

    agent = Agent(
        organization_id=org.id,
        name="FinanceAgent",
        description="Autonomous Finance Agent",
        status="ACTIVE",
    )
    db_session.add(agent)
    db_session.flush()

    raw_key, key_prefix, key_hash = generate_api_key(prefix="ag_agent")
    api_key = APIKey(
        organization_id=org.id,
        agent_id=agent.id,
        name="FinanceAgentKey",
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
    )
    db_session.add(api_key)

    # Grant permission for process_refund
    refund_tool = (
        db_session.query(Tool)
        .filter(Tool.organization_id == org.id, Tool.name == "process_refund")
        .first()
    )
    assert refund_tool is not None, "process_refund tool was not seeded"
    perm = AgentToolPermission(
        agent_id=agent.id,
        tool_id=refund_tool.id,
        organization_id=org.id,
        is_allowed=True,
    )
    db_session.add(perm)
    db_session.commit()

    return {
        "org": org,
        "org_slug": org_slug,
        "agent": agent,
        "tool": refund_tool,
        "agent_headers": {"X-API-Key": raw_key},
    }


def _create_pending_refund_request(client: TestClient, hitl_env: dict) -> str:
    """Helper to call /guard/check for process_refund and return request_id."""
    r = client.post(
        "/api/v1/guard/check",
        headers=hitl_env["agent_headers"],
        json={
            "agent_id": str(hitl_env["agent"].id),
            "tool_name": "process_refund",
            "action": "refund",
            "parameters": {"customer_id": "CUST-1234", "amount": 250.0, "reason": "damaged item"},
        },
    )
    assert r.status_code == 200, f"guard/check failed: {r.status_code} - {r.text}"
    data = r.json()
    assert data["decision"] == "PENDING"
    return data["request_id"]


# ===========================================================================
# Test Cases
# ===========================================================================
class TestHITLEngine:
    def test_manager_can_approve_pending_request(self, db_session, hitl_env):
        """1. MANAGER can approve pending request, executing mock process_refund."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)

            # Find HITL request
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()
            assert hitl is not None
            assert hitl.status == "PENDING"

            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")
            r = client.post(
                f"/api/v1/hitl/{hitl.id}/approve",
                headers=mgr_headers,
                json={"review_notes": "Approved by Manager"},
            )
            assert r.status_code == 200, r.text
            res_data = r.json()
            assert res_data["status"] == "APPROVED"
            assert res_data["review_notes"] == "Approved by Manager"
            assert res_data["reviewer_id"] is not None
            assert res_data["output_payload"] is not None
            assert res_data["output_payload"]["status"] == "completed"
            assert res_data["output_payload"]["amount"] == 250.0

            # Verify in DB
            db_session.expire_all()
            db_hitl = db_session.query(HITLRequest).filter(HITLRequest.id == hitl.id).first()
            assert db_hitl.status == "APPROVED"
            assert db_hitl.reviewed_at is not None

            tool_req = db_session.query(ToolRequest).filter(ToolRequest.id == req_id).first()
            assert tool_req.decision == "APPROVED"
            assert tool_req.output_payload["status"] == "completed"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_manager_can_deny_pending_request(self, db_session, hitl_env):
        """2. MANAGER can deny pending request; mock handler is never executed."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()

            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")
            with patch.object(mock_tools, "process_refund") as mock_fn:
                r = client.post(
                    f"/api/v1/hitl/{hitl.id}/deny",
                    headers=mgr_headers,
                    json={"review_notes": "Denied: Refund amount too high"},
                )
                assert r.status_code == 200, r.text
                res_data = r.json()
                assert res_data["status"] == "DENIED"
                assert res_data["review_notes"] == "Denied: Refund amount too high"
                mock_fn.assert_not_called()

            db_session.expire_all()
            tool_req = db_session.query(ToolRequest).filter(ToolRequest.id == req_id).first()
            assert tool_req.decision == "DENIED"
            assert tool_req.output_payload is None
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_admin_can_approve_and_deny(self, db_session, hitl_env):
        """3. ADMIN role can also approve and deny HITL requests."""
        client = _http_client_for_session(db_session)
        try:
            admin_headers = _register_and_login(client, hitl_env["org_slug"], role="ADMIN")

            req_id1 = _create_pending_refund_request(client, hitl_env)
            hitl1 = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id1).first()
            r1 = client.post(f"/api/v1/hitl/{hitl1.id}/approve", headers=admin_headers)
            assert r1.status_code == 200
            assert r1.json()["status"] == "APPROVED"

            req_id2 = _create_pending_refund_request(client, hitl_env)
            hitl2 = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id2).first()
            r2 = client.post(f"/api/v1/hitl/{hitl2.id}/deny", headers=admin_headers)
            assert r2.status_code == 200
            assert r2.json()["status"] == "DENIED"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_forbidden_roles_cannot_review(self, db_session, hitl_env):
        """4. Non-MANAGER/ADMIN roles (DEVELOPER, AUDITOR, SECURITY) receive 403."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()

            for role in ("DEVELOPER", "AUDITOR", "SECURITY"):
                headers = _register_and_login(client, hitl_env["org_slug"], role=role)
                r_list = client.get("/api/v1/hitl", headers=headers)
                assert r_list.status_code == 403, f"Expected 403 for {role} on GET /hitl"

                r_get = client.get(f"/api/v1/hitl/{hitl.id}", headers=headers)
                assert r_get.status_code == 403, f"Expected 403 for {role} on GET /hitl/{{id}}"

                r_app = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=headers)
                assert r_app.status_code == 403, f"Expected 403 for {role} on POST approve"

                r_den = client.post(f"/api/v1/hitl/{hitl.id}/deny", headers=headers)
                assert r_den.status_code == 403, f"Expected 403 for {role} on POST deny"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_unauthenticated_request_rejected(self, db_session, hitl_env):
        """5. Requests without authorization token receive 401."""
        client = _http_client_for_session(db_session)
        try:
            fake_id = uuid.uuid4()
            assert client.get("/api/v1/hitl").status_code == 401
            assert client.get(f"/api/v1/hitl/{fake_id}").status_code == 401
            assert client.post(f"/api/v1/hitl/{fake_id}/approve").status_code == 401
            assert client.post(f"/api/v1/hitl/{fake_id}/deny").status_code == 401
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_approving_executes_mock_handler_exactly_once(self, db_session, hitl_env):
        """6. Approving a request executes the registered mock handler exactly once."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()
            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")

            with patch.object(mock_tools, "process_refund", wraps=mock_tools.process_refund) as mock_spy:
                r = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=mgr_headers)
                assert r.status_code == 200
                assert mock_spy.call_count == 1
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_already_resolved_request_rejected(self, db_session, hitl_env):
        """7. Approving or denying an already-resolved request returns 400."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()
            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")

            # First approval succeeds
            r1 = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=mgr_headers)
            assert r1.status_code == 200

            # Second approval fails
            r2 = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=mgr_headers)
            assert r2.status_code == 400
            assert "already resolved" in r2.json()["detail"].lower()

            # Deny on already-approved fails
            r3 = client.post(f"/api/v1/hitl/{hitl.id}/deny", headers=mgr_headers)
            assert r3.status_code == 400
            assert "already resolved" in r3.json()["detail"].lower()
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_expired_request_rejected_on_approve_and_deny(self, db_session, hitl_env):
        """8. Requests past expiration are marked EXPIRED and rejected with 400."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()

            # Manually backdate expiration into the past
            past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
            hitl.expires_at = past_time
            db_session.commit()

            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")

            # Approve should fail with expired message
            r_app = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=mgr_headers)
            assert r_app.status_code == 400
            assert "expired" in r_app.json()["detail"].lower()

            # Status should now be EXPIRED
            db_session.expire_all()
            db_hitl = db_session.query(HITLRequest).filter(HITLRequest.id == hitl.id).first()
            assert db_hitl.status == "EXPIRED"

            # Deny on expired also fails
            r_den = client.post(f"/api/v1/hitl/{hitl.id}/deny", headers=mgr_headers)
            assert r_den.status_code == 400
            assert "expired" in r_den.json()["detail"].lower()
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_sweep_expired_hitl_requests_in_isolation(self, db_session, hitl_env):
        """9. sweep_expired_hitl_requests flips only past-expiration pending requests."""
        org_id = hitl_env["org"].id
        now = datetime.now(timezone.utc)

        # Create 2 expired PENDING requests and 2 active PENDING requests
        # We need mock ToolRequest rows for FK
        tool = hitl_env["tool"]
        agent = hitl_env["agent"]

        def _make_req(is_expired: bool) -> HITLRequest:
            tr = ToolRequest(
                id=uuid.uuid4(),
                organization_id=org_id,
                agent_id=agent.id,
                tool_id=tool.id,
                decision="PENDING",
            )
            db_session.add(tr)
            hr = HITLRequest(
                organization_id=org_id,
                tool_request_id=tr.id,
                status="PENDING",
                expires_at=(now - timedelta(hours=1)) if is_expired else (now + timedelta(hours=24)),
            )
            db_session.add(hr)
            return hr

        exp1 = _make_req(is_expired=True)
        exp2 = _make_req(is_expired=True)
        act1 = _make_req(is_expired=False)
        act2 = _make_req(is_expired=False)
        db_session.commit()

        # Run sweep
        sweep_count = sweep_expired_hitl_requests(db_session, organization_id=org_id)
        assert sweep_count >= 2

        db_session.expire_all()
        assert db_session.query(HITLRequest).filter(HITLRequest.id == exp1.id).first().status == "EXPIRED"
        assert db_session.query(HITLRequest).filter(HITLRequest.id == exp2.id).first().status == "EXPIRED"
        assert db_session.query(HITLRequest).filter(HITLRequest.id == act1.id).first().status == "PENDING"
        assert db_session.query(HITLRequest).filter(HITLRequest.id == act2.id).first().status == "PENDING"

    def test_commit_before_execute_ordering_on_approve(self, db_session, hitl_env):
        """10. Approval stands and logs TOOL_EXECUTION_FAILED even if mock handler raises."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()
            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")

            with patch.object(mock_tools, "process_refund", side_effect=RuntimeError("Payment gateway down")):
                r = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=mgr_headers)
                # Approval is committed; endpoint returns 200
                assert r.status_code == 200
                data = r.json()
                assert data["status"] == "APPROVED"
                assert data["output_payload"]["execution_status"] == "error"
                assert "Payment gateway down" in data["output_payload"]["error"]

            db_session.expire_all()
            db_hitl = db_session.query(HITLRequest).filter(HITLRequest.id == hitl.id).first()
            assert db_hitl.status == "APPROVED"

            # Check audit logs: should contain HITL_APPROVED and TOOL_EXECUTION_FAILED
            logs = (
                db_session.query(AuditLog)
                .filter(AuditLog.organization_id == hitl_env["org"].id)
                .order_by(AuditLog.sequence_number.desc())
                .all()
            )
            event_types = [l.event_type for l in logs]
            assert "HITL_APPROVED" in event_types
            assert "TOOL_EXECUTION_FAILED" in event_types
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_approval_with_unregistered_mock_handler(self, db_session, hitl_env):
        """11. Approving a tool with no mock handler records skipped_no_handler."""
        client = _http_client_for_session(db_session)
        try:
            # Create a tool without mock handler
            unhandled_tool = Tool(
                organization_id=hitl_env["org"].id,
                name="custom_unhandled_tool",
                description="Tool with no mock handler",
                risk_level="HIGH",
            )
            db_session.add(unhandled_tool)
            db_session.flush()

            perm = AgentToolPermission(
                agent_id=hitl_env["agent"].id,
                tool_id=unhandled_tool.id,
                organization_id=hitl_env["org"].id,
                is_allowed=True,
            )
            db_session.add(perm)
            db_session.commit()

            # Trigger PENDING via guard
            r_guard = client.post(
                "/api/v1/guard/check",
                headers=hitl_env["agent_headers"],
                json={
                    "agent_id": str(hitl_env["agent"].id),
                    "tool_name": "custom_unhandled_tool",
                    "action": "execute",
                    "parameters": {},
                },
            )
            assert r_guard.status_code == 200
            assert r_guard.json()["decision"] == "PENDING"
            req_id = r_guard.json()["request_id"]

            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()
            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")

            r_app = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=mgr_headers)
            assert r_app.status_code == 200
            data = r_app.json()
            assert data["status"] == "APPROVED"
            assert data["output_payload"]["execution_status"] == "skipped_no_handler"

            # Check audit log
            db_session.expire_all()
            last_log = (
                db_session.query(AuditLog)
                .filter(AuditLog.organization_id == hitl_env["org"].id)
                .order_by(AuditLog.sequence_number.desc())
                .first()
            )
            assert last_log.event_type == "TOOL_EXECUTION_SKIPPED"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_audit_chain_continuity_through_approve_cycle(self, db_session, hitl_env):
        """12. Audit chain remains unbroken and verifiable through guard -> approve -> execute cycle."""
        client = _http_client_for_session(db_session)
        try:
            req_id = _create_pending_refund_request(client, hitl_env)
            hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_id).first()

            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")
            r = client.post(f"/api/v1/hitl/{hitl.id}/approve", headers=mgr_headers)
            assert r.status_code == 200

            # Cryptographic verification of the entire organization's chain
            result = verify_organization_chain(db_session, hitl_env["org"].id)
            assert result["status"] == "VALID", f"Chain verification failed: {result}"
            assert result["total_records"] >= 3
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_finance_agent_refund_demo_scenario_end_to_end(self, db_session, hitl_env):
        """13. Full worked demo scenario:
        FinanceAgent requests refund -> PENDING -> Manager GET /hitl -> approve -> process_refund executes ->
        audit shows PENDING -> APPROVED -> EXECUTED -> verify chain reports VALID.
        """
        client = _http_client_for_session(db_session)
        try:
            # 1. FinanceAgent proposes a large refund
            refund_params = {"customer_id": "CUST-9999", "amount": 5000.0, "reason": "VIP customer exception"}
            r_propose = client.post(
                "/api/v1/guard/check",
                headers=hitl_env["agent_headers"],
                json={
                    "agent_id": str(hitl_env["agent"].id),
                    "tool_name": "process_refund",
                    "action": "execute",
                    "parameters": refund_params,
                },
            )
            assert r_propose.status_code == 200
            guard_data = r_propose.json()
            assert guard_data["decision"] == "PENDING"
            server_req_id = guard_data["request_id"]

            # 2. Manager logs in and views HITL queue
            mgr_headers = _register_and_login(client, hitl_env["org_slug"], role="MANAGER")
            r_queue = client.get("/api/v1/hitl?status=PENDING", headers=mgr_headers)
            assert r_queue.status_code == 200
            queue_data = r_queue.json()
            assert queue_data["total"] >= 1
            target_item = next(item for item in queue_data["items"] if str(item["tool_request_id"]) == server_req_id)
            assert target_item["tool_name"] == "process_refund"
            assert target_item["status"] == "PENDING"
            hitl_id = target_item["id"]

            # 3. Manager approves the refund request
            r_approve = client.post(
                f"/api/v1/hitl/{hitl_id}/approve",
                headers=mgr_headers,
                json={"review_notes": "Approved for VIP customer"},
            )
            assert r_approve.status_code == 200
            approve_data = r_approve.json()
            assert approve_data["status"] == "APPROVED"
            assert approve_data["output_payload"]["status"] == "completed"
            assert approve_data["output_payload"]["amount"] == 5000.0

            # 4. Query audit logs to verify PENDING -> APPROVED -> EXECUTED progression
            # Manager has access to audit via ADMIN role or verify via audit endpoint
            admin_headers = _register_and_login(client, hitl_env["org_slug"], role="ADMIN")
            r_audit = client.get("/api/v1/audit", headers=admin_headers)
            assert r_audit.status_code == 200
            audit_items = r_audit.json()["items"]

            # Audit items are returned reverse-chronological; filter to events for this request
            req_audit_logs = [
                log for log in reversed(audit_items)
                if log.get("payload", {}).get("tool_name") == "process_refund"
                or log.get("payload", {}).get("_tool_name") == "process_refund"
            ]
            decisions = [log["decision"] for log in req_audit_logs]
            assert "PENDING" in decisions
            assert "APPROVED" in decisions
            assert "EXECUTED" in decisions

            # Verify the order of appearance: PENDING occurs before APPROVED occurs before EXECUTED
            idx_pending = decisions.index("PENDING")
            idx_approved = decisions.index("APPROVED")
            idx_executed = decisions.index("EXECUTED")
            assert idx_pending < idx_approved < idx_executed, f"Unexpected decision order: {decisions}"

            # 5. Cryptographic verification of the hash chain
            r_verify = client.post("/api/v1/audit/verify", headers=admin_headers)
            assert r_verify.status_code == 200
            verify_data = r_verify.json()
            assert verify_data["status"] == "VALID"
        finally:
            fastapi_app.dependency_overrides.clear()
