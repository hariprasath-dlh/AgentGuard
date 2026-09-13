"""Tests for Budget endpoints (Phase 12).

Tests cover:
  - POST /agents automatically provisions a budget row
  - GET /budgets lists all budgets for org (scoped)
  - GET /budgets/{id} returns single budget
  - PATCH /budgets/{id} updates caps
  - PATCH with unknown ID returns 404
  - RBAC: AUDITOR and MANAGER can read; only ADMIN/SECURITY can PATCH
  - Org isolation: org-A budgets not visible to org-B
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_headers, login_user, make_unique_slug, register_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_admin(client, slug=None):
    slug = slug or make_unique_slug()
    resp, s = register_user(client, f"admin+{slug}@test.com", slug=slug, role="ADMIN")
    assert resp.status_code == 201
    token = login_user(client, f"admin+{slug}@test.com", slug=s).json()["access_token"]
    return token, s


def _create_user(client, slug, email, role):
    resp, _ = register_user(client, email, slug=slug, role=role)
    assert resp.status_code == 201
    token = login_user(client, email, slug=slug).json()["access_token"]
    return token


def _create_agent(client, token, name="test-agent"):
    resp = client.post(
        "/api/v1/agents",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBudgetDefaultProvisioning:
    def test_create_agent_provisions_budget_row(self, client):
        """POST /agents must auto-create a budget row; GET /budgets must return it."""
        token, _ = _create_admin(client)
        agent = _create_agent(client, token, name="budg-agent")
        agent_id = agent["id"]

        resp = client.get("/api/v1/budgets", headers=auth_headers(token))
        assert resp.status_code == 200
        budgets = resp.json()
        assert any(b["agent_id"] == agent_id for b in budgets), (
            "No budget row found for the newly created agent"
        )

    def test_default_budget_has_null_caps(self, client):
        """Default budget should have all caps as None (unlimited)."""
        token, _ = _create_admin(client)
        _create_agent(client, token, name="null-cap-agent")

        resp = client.get("/api/v1/budgets", headers=auth_headers(token))
        assert resp.status_code == 200
        budget = resp.json()[-1]  # most recent
        assert budget["max_requests_per_minute"] is None
        assert budget["max_requests_per_day"] is None
        assert budget["max_budget_per_session"] is None
        assert budget["max_budget_per_day"] is None


class TestBudgetCRUD:
    def test_get_budget_by_id(self, client):
        token, _ = _create_admin(client)
        _create_agent(client, token, name="get-by-id-agent")

        budgets = client.get("/api/v1/budgets", headers=auth_headers(token)).json()
        assert len(budgets) >= 1
        bid = budgets[0]["id"]

        resp = client.get(f"/api/v1/budgets/{bid}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == bid

    def test_patch_budget_updates_caps(self, client):
        token, _ = _create_admin(client)
        _create_agent(client, token, name="patch-budget-agent")

        budgets = client.get("/api/v1/budgets", headers=auth_headers(token)).json()
        bid = budgets[-1]["id"]

        resp = client.patch(
            f"/api/v1/budgets/{bid}",
            json={"max_requests_per_minute": 60, "max_budget_per_day": "10.00"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_requests_per_minute"] == 60
        assert float(data["max_budget_per_day"]) == 10.0

    def test_patch_nonexistent_budget_returns_404(self, client):
        token, _ = _create_admin(client)
        resp = client.patch(
            f"/api/v1/budgets/{uuid.uuid4()}",
            json={"max_requests_per_day": 100},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestBudgetRBAC:
    def test_auditor_can_list(self, client):
        admin_token, slug = _create_admin(client)
        _create_agent(client, admin_token, name="aud-budg-agent")
        auditor_token = _create_user(client, slug, f"aud+{slug}@test.com", "AUDITOR")
        resp = client.get("/api/v1/budgets", headers=auth_headers(auditor_token))
        assert resp.status_code == 200

    def test_manager_can_list(self, client):
        admin_token, slug = _create_admin(client)
        _create_agent(client, admin_token, name="mgr-budg-agent")
        mgr_token = _create_user(client, slug, f"mgr+{slug}@test.com", "MANAGER")
        resp = client.get("/api/v1/budgets", headers=auth_headers(mgr_token))
        assert resp.status_code == 200

    def test_auditor_cannot_patch(self, client):
        admin_token, slug = _create_admin(client)
        _create_agent(client, admin_token, name="aud-patch-agent")
        budgets = client.get("/api/v1/budgets", headers=auth_headers(admin_token)).json()
        bid = budgets[-1]["id"]
        auditor_token = _create_user(client, slug, f"audpatch+{slug}@test.com", "AUDITOR")
        resp = client.patch(
            f"/api/v1/budgets/{bid}",
            json={"max_requests_per_day": 5},
            headers=auth_headers(auditor_token),
        )
        assert resp.status_code == 403

    def test_manager_cannot_patch(self, client):
        admin_token, slug = _create_admin(client)
        _create_agent(client, admin_token, name="mgr-patch-agent")
        budgets = client.get("/api/v1/budgets", headers=auth_headers(admin_token)).json()
        bid = budgets[-1]["id"]
        mgr_token = _create_user(client, slug, f"mgrpatch+{slug}@test.com", "MANAGER")
        resp = client.patch(
            f"/api/v1/budgets/{bid}",
            json={"max_requests_per_day": 5},
            headers=auth_headers(mgr_token),
        )
        assert resp.status_code == 403


class TestBudgetOrgIsolation:
    def test_org_a_cannot_see_org_b_budgets(self, client):
        token_a, _ = _create_admin(client)
        token_b, _ = _create_admin(client)

        _create_agent(client, token_a, name="iso-agent-a")

        resp = client.get("/api/v1/budgets", headers=auth_headers(token_b))
        assert resp.status_code == 200
        # org-B should have no budgets (no agents created there)
        assert len(resp.json()) == 0


class TestBudgetUnlimitedCaps:
    def test_agent_with_null_budget_caps_passes_budget_check_regardless_of_spend(self, db_session):
        """Explicitly proves that an agent with None/unlimited budget caps passes
        the BUDGET check regardless of accumulated spend or proposed request cost."""
        from decimal import Decimal
        from unittest.mock import MagicMock
        from app.models.agent import Agent
        from app.models.budget import Budget
        from app.models.organization import Organization
        from app.models.tool import Tool
        from app.schemas.policy import DecisionInput
        from app.services.budget_guard import RedisBudgetChecker

        org = Organization(name="Unlimited Org", slug=f"unlimited-{uuid.uuid4().hex[:6]}")
        db_session.add(org)
        db_session.flush()

        agent = Agent(
            organization_id=org.id,
            name="UnlimitedBudgetAgent",
            status="ACTIVE",
        )
        tool = Tool(
            organization_id=org.id,
            name="high_spend_tool",
            risk_level="LOW",
            is_active=True,
        )
        db_session.add_all([agent, tool])
        db_session.flush()

        # Provision a budget row with ALL CAPS as None (unlimited), and existing high spend
        budget = Budget(
            organization_id=org.id,
            agent_id=agent.id,
            max_requests_per_minute=None,
            max_requests_per_day=None,
            max_budget_per_session=None,
            max_budget_per_day=None,
            current_spend=Decimal("999999.99"),
        )
        db_session.add(budget)
        db_session.flush()

        # Mock Redis pipeline returning existing massive spend ($50,000 session, $100,000 daily)
        mock_redis = MagicMock()
        pipe = mock_redis.pipeline.return_value
        pipe.execute.return_value = [b"50000.00", b"100000.00", 1000, 5000]

        checker = RedisBudgetChecker(mock_redis)

        # Propose another massive request: $25,000 cost
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name="high_spend_tool",
            action="execute",
            estimated_cost=25000.00,
            estimated_tokens=500,
        )

        allowed, reason = checker(db_session, inp, agent, tool)
        assert allowed is True, f"Expected ALLOW with unlimited budget, got: {reason}"
        assert reason is None

        # Contrast with capped budget: set daily cap to $50, and verify it DENIES
        budget.max_budget_per_day = Decimal("50.00")
        db_session.flush()

        allowed_capped, reason_capped = checker(db_session, inp, agent, tool)
        assert allowed_capped is False
        assert "Daily budget limit exceeded" in reason_capped


class TestBudgetBackfill:
    def test_backfill_missing_budgets_provisions_unlimited_row(self, db_session):
        """Verifies that the backfill script provisions missing budget rows for existing agents and is idempotent."""
        from app.models.agent import Agent
        from app.models.budget import Budget
        from app.models.organization import Organization
        from app.scripts.backfill_budgets import backfill_missing_budgets

        org = Organization(name="Backfill Org", slug=f"backfill-{uuid.uuid4().hex[:6]}")
        db_session.add(org)
        db_session.flush()

        # Create two legacy agents WITHOUT any budget row
        agent1 = Agent(organization_id=org.id, name="LegacyAgent1", status="ACTIVE")
        agent2 = Agent(organization_id=org.id, name="LegacyAgent2", status="ACTIVE")
        db_session.add_all([agent1, agent2])
        db_session.commit()

        # Verify no budget rows exist for them yet
        existing_budgets = db_session.query(Budget).filter(Budget.agent_id.in_([agent1.id, agent2.id])).all()
        assert len(existing_budgets) == 0

        # Run backfill
        created_count = backfill_missing_budgets(db_session)
        assert created_count == 2

        # Verify both agents now have a budget row with None caps
        b1 = db_session.query(Budget).filter(Budget.agent_id == agent1.id).first()
        b2 = db_session.query(Budget).filter(Budget.agent_id == agent2.id).first()
        assert b1 is not None and b1.max_budget_per_day is None and b1.max_budget_per_session is None
        assert b2 is not None and b2.max_budget_per_day is None and b2.max_budget_per_session is None

        # Idempotency check: running backfill a second time should create 0 rows
        second_run_count = backfill_missing_budgets(db_session)
        assert second_run_count == 0
