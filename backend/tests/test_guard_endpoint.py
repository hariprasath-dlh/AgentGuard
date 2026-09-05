"""Integration and unit tests for the Pre-Dispatch Gateway (Phase 7).

Tests POST /api/v1/guard/check against real Postgres and Redis:
  1. DENY from policy engine never calls mock tool
  2. ALLOW for read_customer calls mock handler exactly once
  3. ALLOW for create_ticket calls mock handler exactly once
  4. ALLOW for send_email calls mock handler exactly once
  5. PENDING for process_refund (HIGH risk) creates hitl_requests row and calls no mock handler
  6. Every decision produces exactly one audit_logs row with monotonic sequence_number and linked FK
  7. Simulated audit-write failure returns HTTP 500 AND does not call mock handler
  8. Unauthenticated request rejected with 401 before policy engine is invoked
  9. delete_database (CRITICAL risk) returns DENY and cannot execute
 10. ALLOW for a tool without a mock handler records 'skipped_no_handler' in audit & output payload
 11. Mock handler exception does not crash endpoint, returns ALLOW, records error in output_payload
"""
import uuid
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.seed import seed
from app.models.agent import Agent
from app.models.api_key import APIKey
from app.models.audit_log import AuditLog
from app.models.hitl_request import HITLRequest
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.models.tool_request import ToolRequest
from app.security.api_key import generate_api_key
from app.services import mock_tools


@pytest.fixture
def guard_env(db_session: Session):
    """Set up organization, agent, API key, and seeded demo tools."""
    org_slug = f"guard-org-{uuid.uuid4().hex[:6]}"
    org = Organization(name="Guard Test Org", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    # Seed the 5 demo tools for this org
    seed(db_session, org_slug=org_slug)

    agent = Agent(
        organization_id=org.id,
        name="TestGovAgent",
        description="Autonomous Governance Test Agent",
        status="ACTIVE",
    )
    db_session.add(agent)
    db_session.flush()

    raw_key, key_prefix, key_hash = generate_api_key(prefix="ag_agent")
    api_key = APIKey(
        organization_id=org.id,
        agent_id=agent.id,
        name="TestGovAgentKey",
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
    )
    db_session.add(api_key)
    db_session.commit()

    return {
        "org": org,
        "agent": agent,
        "api_key": raw_key,
        "headers": {"X-API-Key": raw_key},
    }


def _grant_permission(db_session: Session, org_id: uuid.UUID, agent_id: uuid.UUID, tool_name: str):
    tool = db_session.query(Tool).filter(Tool.organization_id == org_id, Tool.name == tool_name).first()
    assert tool is not None, f"Tool '{tool_name}' must exist in seeded tools"
    perm = AgentToolPermission(
        organization_id=org_id,
        agent_id=agent_id,
        tool_id=tool.id,
        is_allowed=True,
    )
    db_session.add(perm)
    db_session.commit()
    return tool


class TestGuardEndpoint:
    def test_guard_deny_never_calls_mock_tool(self, client, db_session, guard_env):
        """1. DENY from policy engine (no permission) never invokes the mock handler."""
        # Note: Do not grant permission for read_customer
        with patch.object(mock_tools, "read_customer") as mock_read:
            resp = client.post(
                "/api/v1/guard/check",
                json={
                    "agent_id": str(guard_env["agent"].id),
                    "tool_name": "read_customer",
                    "action": "fetch",
                    "parameters": {"customer_id": "CUST-999"},
                },
                headers=guard_env["headers"],
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["decision"] == "DENY"
            assert "no permission grant" in body["reason"].lower()
            mock_read.assert_not_called()

    def test_guard_allow_read_customer_calls_mock_tool_once(self, client, db_session, guard_env):
        """2. ALLOW for read_customer invokes mock handler exactly once and saves output."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "read_customer")

        with patch.object(mock_tools, "read_customer", wraps=mock_tools.read_customer) as mock_read:
            resp = client.post(
                "/api/v1/guard/check",
                json={
                    "agent_id": str(guard_env["agent"].id),
                    "tool_name": "read_customer",
                    "action": "fetch",
                    "parameters": {"customer_id": "CUST-42"},
                },
                headers=guard_env["headers"],
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["decision"] == "ALLOW"
            mock_read.assert_called_once_with({"customer_id": "CUST-42"})

            # Verify output payload in database
            tool_req = db_session.query(ToolRequest).filter(ToolRequest.id == uuid.UUID(body["request_id"])).first()
            assert tool_req is not None
            assert tool_req.output_payload is not None
            assert tool_req.output_payload["customer_id"] == "CUST-42"
            assert tool_req.decision == "ALLOW"

    def test_guard_allow_create_ticket_calls_mock_tool_once(self, client, db_session, guard_env):
        """3. ALLOW for create_ticket invokes mock handler exactly once."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "create_ticket")

        with patch.object(mock_tools, "create_ticket", wraps=mock_tools.create_ticket) as mock_ticket:
            resp = client.post(
                "/api/v1/guard/check",
                json={
                    "agent_id": str(guard_env["agent"].id),
                    "tool_name": "create_ticket",
                    "action": "create",
                    "parameters": {"subject": "Urgent outage", "priority": "high"},
                },
                headers=guard_env["headers"],
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["decision"] == "ALLOW"
            mock_ticket.assert_called_once_with({"subject": "Urgent outage", "priority": "high"})

            tool_req = db_session.query(ToolRequest).filter(ToolRequest.id == uuid.UUID(body["request_id"])).first()
            assert tool_req is not None
            assert "ticket_id" in tool_req.output_payload

    def test_guard_allow_send_email_calls_mock_tool_once(self, client, db_session, guard_env):
        """4. ALLOW for send_email (MEDIUM risk) invokes mock handler exactly once."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "send_email")

        with patch.object(mock_tools, "send_email", wraps=mock_tools.send_email) as mock_email:
            resp = client.post(
                "/api/v1/guard/check",
                json={
                    "agent_id": str(guard_env["agent"].id),
                    "tool_name": "send_email",
                    "action": "send",
                    "parameters": {"to": "user@example.com", "subject": "Notice"},
                },
                headers=guard_env["headers"],
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["decision"] == "ALLOW"
            mock_email.assert_called_once_with({"to": "user@example.com", "subject": "Notice"})

    def test_guard_pending_process_refund_creates_hitl_no_mock_call(self, client, db_session, guard_env):
        """5. PENDING for process_refund (HIGH risk) creates hitl_requests row and calls no mock handler."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "process_refund")

        resp = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "process_refund",
                "action": "refund",
                "parameters": {"amount": 250.0, "reason": "Customer request"},
            },
            headers=guard_env["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "PENDING"
        assert "hitl" in body["reason"].lower() or "human approval" in body["reason"].lower()

        req_uuid = uuid.UUID(body["request_id"])
        tool_req = db_session.query(ToolRequest).filter(ToolRequest.id == req_uuid).first()
        assert tool_req is not None
        assert tool_req.decision == "PENDING"

        # Verify HITLRequest row created
        hitl = db_session.query(HITLRequest).filter(HITLRequest.tool_request_id == req_uuid).first()
        assert hitl is not None
        assert hitl.status == "PENDING"
        assert hitl.organization_id == guard_env["org"].id

    def test_every_decision_creates_audit_log_and_links_tool_request(self, client, db_session, guard_env):
        """6. Every decision (ALLOW, DENY, PENDING) writes an audit_logs row with sequence_number and FK."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "read_customer")
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "process_refund")

        # 1st request: ALLOW
        r1 = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "read_customer",
                "action": "fetch",
                "parameters": {"customer_id": "CUST-1"},
            },
            headers=guard_env["headers"],
        )
        assert r1.json()["decision"] == "ALLOW"

        # 2nd request: DENY (unpermitted tool)
        r2 = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "create_ticket",
                "action": "create",
                "parameters": {},
            },
            headers=guard_env["headers"],
        )
        assert r2.json()["decision"] == "DENY"

        # 3rd request: PENDING (HIGH risk process_refund)
        r3 = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "process_refund",
                "action": "refund",
                "parameters": {"amount": 50.0},
            },
            headers=guard_env["headers"],
        )
        assert r3.json()["decision"] == "PENDING"

        # Verify 3 audit log entries with monotonic sequence numbers 1, 2, 3
        logs = (
            db_session.query(AuditLog)
            .filter(AuditLog.organization_id == guard_env["org"].id)
            .order_by(AuditLog.sequence_number.asc())
            .all()
        )
        assert len(logs) == 3
        assert [log.sequence_number for log in logs] == [1, 2, 3]
        assert [log.decision for log in logs] == ["ALLOW", "DENY", "PENDING"]

        # Phase 8: Verify real SHA-256 hash chain linkage (no more placeholder zeros)
        GENESIS_HASH = "0" * 64
        import re
        sha256_pattern = re.compile(r"^[0-9a-f]{64}$")

        # First record: previous_hash must be the genesis hash
        assert logs[0].previous_hash == GENESIS_HASH, "seq=1 must chain from GENESIS_HASH"
        assert sha256_pattern.match(logs[0].current_hash), "seq=1 current_hash must be 64-char hex"
        assert logs[0].current_hash != GENESIS_HASH, "seq=1 current_hash must not equal GENESIS_HASH"

        # Each subsequent record: previous_hash == prior record's current_hash
        for i in range(1, len(logs)):
            assert logs[i].previous_hash == logs[i - 1].current_hash, (
                f"seq={logs[i].sequence_number} previous_hash must link to seq={logs[i-1].sequence_number} current_hash"
            )
            assert sha256_pattern.match(logs[i].current_hash), (
                f"seq={logs[i].sequence_number} current_hash must be 64-char hex"
            )
            assert logs[i].current_hash != logs[i - 1].current_hash, (
                f"seq={logs[i].sequence_number} must have a different current_hash from prior record"
            )

        for log in logs:
            assert log.event_type == "TOOL_REQUEST_EVALUATED"

        # Verify FK linkage between ToolRequest and AuditLog
        req1 = db_session.query(ToolRequest).filter(ToolRequest.id == uuid.UUID(r1.json()["request_id"])).first()
        assert req1.audit_log_id == logs[0].id

    def test_audit_write_failure_returns_500_and_does_not_call_mock_tool(self, client, db_session, guard_env):
        """7. Commit-before-execute safety: If audit commit fails, returns 500 and mock handler is NOT called."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "read_customer")

        with patch.object(mock_tools, "read_customer") as mock_read, \
             patch.object(Session, "commit", side_effect=SQLAlchemyError("Simulated DB commit error")):

            resp = client.post(
                "/api/v1/guard/check",
                json={
                    "agent_id": str(guard_env["agent"].id),
                    "tool_name": "read_customer",
                    "action": "fetch",
                    "parameters": {"customer_id": "CUST-FAIL"},
                },
                headers=guard_env["headers"],
            )
            assert resp.status_code == 500
            assert "Failed to record audit trail" in resp.json()["detail"]
            # CRITICAL SAFETY ASSERTION: mock tool was never invoked
            mock_read.assert_not_called()

    def test_unauthenticated_request_rejected_401(self, client, guard_env):
        """8. Unauthenticated requests are rejected with 401 before policy engine runs."""
        # No header
        r1 = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "read_customer",
                "action": "fetch",
            },
        )
        assert r1.status_code == 401

        # Invalid key
        r2 = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "read_customer",
                "action": "fetch",
            },
            headers={"X-API-Key": "ag_agent_invalidkey1234567890"},
        )
        assert r2.status_code == 401

    def test_delete_database_critical_risk_denied_no_mock_execution(self, client, db_session, guard_env):
        """9. delete_database has CRITICAL risk level: always DENY, no execution possible."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "delete_database")

        resp = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "delete_database",
                "action": "purge",
                "parameters": {"confirm": "yes"},
            },
            headers=guard_env["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "DENY"
        assert "risk level 'CRITICAL', which is denied by policy" in body["reason"]

        # Confirm no mock handler even exists in mock_tools
        assert mock_tools.get_handler("delete_database") is None

    def test_allow_with_no_mock_handler_records_skipped_no_handler(self, client, db_session, guard_env):
        """10. An ALLOW decision for a tool with no mock handler records 'skipped_no_handler' in audit trail."""
        # Create a custom tool with LOW risk
        custom_tool = Tool(
            organization_id=guard_env["org"].id,
            name="custom_api_tool",
            description="Tool without mock handler",
            risk_level="LOW",
            is_active=True,
        )
        db_session.add(custom_tool)
        db_session.flush()

        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "custom_api_tool")

        resp = client.post(
            "/api/v1/guard/check",
            json={
                "agent_id": str(guard_env["agent"].id),
                "tool_name": "custom_api_tool",
                "action": "invoke",
                "parameters": {"key": "value"},
            },
            headers=guard_env["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "ALLOW"

        req_uuid = uuid.UUID(body["request_id"])
        tool_req = db_session.query(ToolRequest).filter(ToolRequest.id == req_uuid).first()
        assert tool_req is not None
        assert tool_req.output_payload == {
            "execution_status": "skipped_no_handler",
            "reason": "No mock handler registered for tool 'custom_api_tool'",
        }

        # Check audit log payload
        audit_log = db_session.query(AuditLog).filter(AuditLog.id == tool_req.audit_log_id).first()
        assert audit_log is not None
        assert audit_log.payload.get("execution_status") == "skipped_no_handler"

    def test_mock_handler_exception_returns_allow_and_records_error(self, client, db_session, guard_env):
        """11. An exception in the mock handler does not crash the endpoint: returns ALLOW and logs error."""
        _grant_permission(db_session, guard_env["org"].id, guard_env["agent"].id, "read_customer")

        with patch.object(mock_tools, "read_customer", side_effect=RuntimeError("Internal tool failure")):
            resp = client.post(
                "/api/v1/guard/check",
                json={
                    "agent_id": str(guard_env["agent"].id),
                    "tool_name": "read_customer",
                    "action": "fetch",
                    "parameters": {"customer_id": "CUST-CRASH"},
                },
                headers=guard_env["headers"],
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["decision"] == "ALLOW"

            tool_req = db_session.query(ToolRequest).filter(ToolRequest.id == uuid.UUID(body["request_id"])).first()
            assert tool_req is not None
            assert tool_req.output_payload == {
                "execution_status": "error",
                "error": "Internal tool failure",
            }
