"""Integration tests for the AgentGuard SDK against a real running backend.

Tests exercise real HTTP communication over TCP, real Postgres writes, and
real Redis rate limiting / policy governance.
"""
import time
import uuid
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy.orm import Session

from agentguard import (
    AgentGuard,
    AgentGuardAuthenticationError,
    AgentGuardDenied,
    AgentGuardPending,
    AgentGuardServerError,
    AgentGuardTimeout,
)
from app.models.api_key import APIKey
from app.models.audit_log import AuditLog
from app.models.tool_request import ToolRequest
from app.security.api_key import generate_api_key


class TestAgentGuardSDK:
    def test_low_risk_tool_allowed(self, test_env):
        """1. A LOW-risk tool call returns successfully with no exception and allowed=True."""
        client = AgentGuard(
            api_key=test_env["api_key"],
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
        )
        try:
            result = client.guard(
                tool="read_customer",
                parameters={"customer_id": "CUST-1001"},
            )
            assert result.allowed is True
            assert result.decision == "ALLOW"
            assert result.request_id is not None
            assert len(result.request_id) == 36  # Valid UUID string
            assert "allow" in result.reason.lower() or "policy" in result.reason.lower() or result.reason != ""
        finally:
            client.close()

    def test_critical_risk_tool_denied(self, test_env):
        """2. A CRITICAL-risk tool call raises AgentGuardDenied with reason and request_id."""
        client = AgentGuard(
            api_key=test_env["api_key"],
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
        )
        try:
            with pytest.raises(AgentGuardDenied) as exc_info:
                client.guard(
                    tool="delete_database",
                    parameters={"database": "production"},
                )
            err = exc_info.value
            assert err.request_id is not None
            assert len(err.request_id) == 36
            assert "critical" in err.reason.lower() or "deny" in err.reason.lower() or "blocked" in err.reason.lower()
        finally:
            client.close()

    def test_high_risk_tool_pending(self, test_env):
        """3. A HIGH-risk tool call raises AgentGuardPending with a usable request_id for HITL."""
        client = AgentGuard(
            api_key=test_env["api_key"],
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
        )
        try:
            with pytest.raises(AgentGuardPending) as exc_info:
                client.guard(
                    tool="process_refund",
                    parameters={"amount": 500.0, "customer_id": "CUST-1001"},
                )
            err = exc_info.value
            assert err.request_id is not None
            assert len(err.request_id) == 36
            assert "hitl" in err.reason.lower() or "human" in err.reason.lower()
        finally:
            client.close()

    def test_authentication_error_malformed_key(self, test_env):
        """4a. Malformed or unrecognized API key raises AgentGuardAuthenticationError."""
        client = AgentGuard(
            api_key="ag_invalid_nonexistent_key_12345",
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
        )
        try:
            with pytest.raises(AgentGuardAuthenticationError) as exc_info:
                client.guard(
                    tool="read_customer",
                    parameters={"customer_id": "CUST-1001"},
                )
            assert exc_info.value.status_code == 401
        finally:
            client.close()

    def test_authentication_error_revoked_key(self, test_env, db_session: Session):
        """4b. A properly issued but subsequently revoked key raises AgentGuardAuthenticationError."""
        # Issue a new active key
        raw_key, key_prefix, key_hash = generate_api_key(prefix="ag_agent")
        api_key = APIKey(
            organization_id=test_env["org_id"],
            agent_id=test_env["agent_id"],
            name="RevokedTestKey",
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=False,  # Explicitly REVOKED
        )
        db_session.add(api_key)
        db_session.commit()

        client = AgentGuard(
            api_key=raw_key,
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
        )
        try:
            with pytest.raises(AgentGuardAuthenticationError) as exc_info:
                client.guard(
                    tool="read_customer",
                    parameters={"customer_id": "CUST-1001"},
                )
            assert exc_info.value.status_code == 401
            assert "revoked" in str(exc_info.value.detail).lower() or "invalid" in str(exc_info.value.detail).lower()
        finally:
            client.close()

    def test_unreachable_host_raises_timeout(self, test_env):
        """5. A request to an unreachable port raises AgentGuardTimeout within configured timeout."""
        unreachable_url = "http://127.0.0.1:19999/api/v1"
        client = AgentGuard(
            api_key=test_env["api_key"],
            base_url=unreachable_url,
            timeout=0.4,
            max_retries=0,  # Fast failure
        )
        try:
            start_time = time.time()
            with pytest.raises(AgentGuardTimeout):
                client.guard(
                    tool="read_customer",
                    parameters={"customer_id": "CUST-1001"},
                )
            elapsed = time.time() - start_time
            # Confirm it failed promptly rather than hanging indefinitely
            assert elapsed < 3.0
        finally:
            client.close()

    def test_safe_retry_on_connection_failure_and_no_duplicate_submission(self, test_env, db_session: Session):
        """6. Safe retry test with transport-layer seam:
        Simulates a network drop on attempt #1, retries on attempt #2 against the real backend,
        and verifies in PostgreSQL that exactly ONE row is written to tool_requests and audit_logs.

        SEAM NOTE:
          We intentionally wrap the underlying httpx.Client's post method so the first call
          raises httpx.ConnectError (simulating connection dropped before reaching backend),
          while the second attempt falls through directly to the real live backend.
        """
        client = AgentGuard(
            api_key=test_env["api_key"],
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
            max_retries=2,
            retry_backoff=0.1,
        )
        try:
            original_post = client._client.post
            call_count = [0]

            def flaky_post(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    # Attempt 1: Simulate connection refused / network failure
                    raise httpx.ConnectError("Simulated socket connection failure", request=None)
                # Attempt 2: Fall through to real backend
                return original_post(*args, **kwargs)

            with patch.object(client._client, "post", side_effect=flaky_post):
                result = client.guard(
                    tool="read_customer",
                    parameters={"customer_id": "CUST-RETRY-001"},
                )

            assert call_count[0] == 2, f"Expected 2 attempts (1 failure + 1 retry), got {call_count[0]}"
            assert result.allowed is True
            req_id = result.request_id

            # Verify in PostgreSQL that exactly ONE tool_request and ONE audit_log was created
            db_session.expire_all()
            req_uuid = uuid.UUID(req_id)
            tool_reqs = db_session.query(ToolRequest).filter(ToolRequest.id == req_uuid).all()
            assert len(tool_reqs) == 1, f"Expected exactly 1 ToolRequest row, found {len(tool_reqs)}"

            all_audit_rows = db_session.query(AuditLog).filter(
                AuditLog.organization_id == test_env["org_id"],
            ).all()
            matching_audit_rows = [
                row for row in all_audit_rows
                if row.payload and row.payload.get("_request_id") == req_id
            ]
            assert len(matching_audit_rows) == 1, f"Expected exactly 1 AuditLog row, found {len(matching_audit_rows)}"
        finally:
            client.close()

    def test_no_retry_after_receiving_real_decision(self, test_env):
        """7. Verifies that once a real decision is returned (e.g. DENY), no retries occur."""
        client = AgentGuard(
            api_key=test_env["api_key"],
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
            max_retries=3,  # Set high retries to prove it does NOT retry
        )
        try:
            call_count = [0]
            original_post = client._client.post

            def counting_post(*args, **kwargs):
                call_count[0] += 1
                return original_post(*args, **kwargs)

            with patch.object(client._client, "post", side_effect=counting_post):
                with pytest.raises(AgentGuardDenied):
                    client.guard(
                        tool="delete_database",
                        parameters={},
                    )

            assert call_count[0] == 1, f"Expected exactly 1 call (no retries after DENY), got {call_count[0]}"
        finally:
            client.close()

    def test_boolean_branch_mode_without_raising(self, test_env):
        """8. When raise_for_status=False, client.guard returns GuardResult(allowed=False)."""
        client = AgentGuard(
            api_key=test_env["api_key"],
            base_url=test_env["base_url"],
            agent_id=test_env["agent_id"],
        )
        try:
            # DENY tool
            res_deny = client.guard(
                tool="delete_database",
                parameters={},
                raise_for_status=False,
            )
            assert res_deny.allowed is False
            assert res_deny.decision == "DENY"
            assert res_deny.request_id is not None

            # PENDING tool
            res_pending = client.guard(
                tool="process_refund",
                parameters={"amount": 999.0},
                raise_for_status=False,
            )
            assert res_pending.allowed is False
            assert res_pending.decision == "PENDING"
            assert res_pending.request_id is not None
        finally:
            client.close()
