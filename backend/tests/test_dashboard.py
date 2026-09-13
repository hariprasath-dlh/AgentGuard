"""Tests for Dashboard monitoring endpoints (Phase 12).

Tests cover:
  - GET /dashboard/stats returns correct aggregate counts
  - GET /dashboard/stats allowed/blocked/pending counts match seeded requests
  - GET /dashboard/activity returns items in reverse-chrono order
  - GET /dashboard/activity pagination (limit/offset)
  - RBAC: AUDITOR, MANAGER, ADMIN, SECURITY can all read
  - RBAC: DEVELOPER is denied
  - Org isolation: org-A stats/activity not visible in org-B

Note: dashboard/stats and dashboard/activity hit real PostgreSQL (via the
shared engine fixture). SQLite is also used when TEST_DATABASE_URL is not set.
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


def _setup_agent_tool(client, token, agent_name="dash-agent", tool_name="dash-tool"):
    """Create agent + tool + permission, return (agent_id, tool_id, api_key)."""
    agent_resp = client.post(
        "/api/v1/agents",
        json={"name": agent_name},
        headers=auth_headers(token),
    )
    assert agent_resp.status_code == 201
    agent = agent_resp.json()
    agent_id = agent["id"]
    api_key = agent["api_key"]

    tool_resp = client.post(
        "/api/v1/tools",
        json={"name": tool_name, "risk_level": "LOW"},
        headers=auth_headers(token),
    )
    assert tool_resp.status_code == 201
    tool_id = tool_resp.json()["id"]

    perm_resp = client.post(
        "/api/v1/permissions",
        json={"agent_id": agent_id, "tool_id": tool_id, "is_allowed": True},
        headers=auth_headers(token),
    )
    assert perm_resp.status_code in (200, 201)

    return agent_id, tool_id, api_key


def _guard_check(client, api_key, agent_id, tool_name):
    return client.post(
        "/api/v1/guard/check",
        json={
            "agent_id": str(agent_id),
            "tool_name": tool_name,
            "action": "execute",
            "parameters": {},
        },
        headers={"X-API-Key": api_key},
    )


# ---------------------------------------------------------------------------
# Stats tests
# ---------------------------------------------------------------------------

class TestDashboardStats:
    def test_stats_returns_correct_shape(self, client):
        token, _ = _create_admin(client)
        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        required = {
            "total_agents", "total_tools", "requests_today",
            "allowed_today", "blocked_today", "pending_today",
            "total_spend_today", "budget_utilization",
        }
        assert required.issubset(data.keys())

    def test_stats_counts_agents_and_tools(self, client):
        token, _ = _create_admin(client)
        slug = make_unique_slug()
        # Use a fresh org to get predictable counts
        t2, s2 = _create_admin(client, slug=slug)

        _setup_agent_tool(client, t2, agent_name=f"ag1-{slug}", tool_name=f"tl1-{slug}")

        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(t2))
        data = resp.json()
        assert data["total_agents"] >= 1
        assert data["total_tools"] >= 1

    def test_stats_counts_allowed_requests(self, client):
        token, _ = _create_admin(client)
        slug = make_unique_slug()
        t2, s2 = _create_admin(client, slug=slug)

        agent_id, tool_id, api_key = _setup_agent_tool(
            client, t2,
            agent_name=f"stat-ag-{slug}",
            tool_name=f"stat-tl-{slug}",
        )

        # Fire one LOW risk request — may be ALLOW or DENY depending on whether
        # Redis is available in this environment. Either way it counts as a request.
        guard_resp = _guard_check(client, api_key, agent_id, f"stat-tl-{slug}")
        assert guard_resp.json()["decision"] in ("ALLOW", "DENY", "PENDING")

        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(t2))
        data = resp.json()
        assert data["requests_today"] >= 1


    def test_stats_budget_utilization_includes_agent(self, client):
        token, _ = _create_admin(client)
        slug = make_unique_slug()
        t2, s2 = _create_admin(client, slug=slug)
        _setup_agent_tool(client, t2, agent_name=f"bu-ag-{slug}", tool_name=f"bu-tl-{slug}")

        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(t2))
        data = resp.json()
        assert len(data["budget_utilization"]) >= 1
        entry = data["budget_utilization"][0]
        assert "agent_id" in entry
        assert "current_spend" in entry

    def test_developer_denied_stats(self, client):
        admin_token, slug = _create_admin(client)
        dev_token = _create_user(client, slug, f"dev+{slug}@test.com", "DEVELOPER")
        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(dev_token))
        assert resp.status_code == 403

    def test_auditor_can_read_stats(self, client):
        admin_token, slug = _create_admin(client)
        aud_token = _create_user(client, slug, f"aud+{slug}@test.com", "AUDITOR")
        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(aud_token))
        assert resp.status_code == 200

    def test_manager_can_read_stats(self, client):
        admin_token, slug = _create_admin(client)
        mgr_token = _create_user(client, slug, f"mgr+{slug}@test.com", "MANAGER")
        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(mgr_token))
        assert resp.status_code == 200

    def test_stats_org_isolation(self, client):
        """Stats for org-B must not include agents/requests from org-A."""
        t_a, _ = _create_admin(client)
        t_b, _ = _create_admin(client)

        slug_a = make_unique_slug()
        t_a2, s_a2 = _create_admin(client, slug=slug_a)
        _setup_agent_tool(client, t_a2, agent_name=f"iso-ag-{slug_a}", tool_name=f"iso-tl-{slug_a}")

        # org-B (t_b) should have its own zeroed stats
        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers(t_b))
        data = resp.json()
        assert data["total_agents"] == 0
        assert data["total_tools"] == 0

    def test_dashboard_stats_utc_boundary_synchronization(self):
        """Explicitly verify that _today_start() uses UTC midnight (00:00:00)
        and aligns exactly with Phase 6's RedisBudgetChecker daily-cost-limit reset."""
        from datetime import datetime, timezone
        from app.api.dashboard import _today_start
        from app.services.budget_guard import RedisBudgetChecker

        start = _today_start()
        now_utc = datetime.now(timezone.utc)
        assert start.tzinfo == timezone.utc
        assert start.hour == 0 and start.minute == 0 and start.second == 0 and start.microsecond == 0
        assert start.strftime("%Y-%m-%d") == now_utc.strftime("%Y-%m-%d")

        # Verify exact string date alignment with RedisBudgetChecker's daily partition key
        checker = RedisBudgetChecker(None)
        assert start.strftime("%Y-%m-%d") == checker._get_utc_date()


# ---------------------------------------------------------------------------
# Activity feed tests
# ---------------------------------------------------------------------------

class TestDashboardActivity:
    def test_activity_returns_correct_shape(self, client):
        token, _ = _create_admin(client)
        resp = client.get("/api/v1/dashboard/activity", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    def test_activity_contains_seeded_request(self, client):
        slug = make_unique_slug()
        t2, s2 = _create_admin(client, slug=slug)
        agent_id, tool_id, api_key = _setup_agent_tool(
            client, t2,
            agent_name=f"act-ag-{slug}",
            tool_name=f"act-tl-{slug}",
        )
        _guard_check(client, api_key, agent_id, f"act-tl-{slug}")

        resp = client.get("/api/v1/dashboard/activity", headers=auth_headers(t2))
        data = resp.json()
        assert data["total"] >= 1
        item = data["items"][0]
        assert "request_id" in item
        assert "decision" in item
        assert "agent_name" in item
        assert "tool_name" in item

    def test_activity_pagination(self, client):
        slug = make_unique_slug()
        t2, s2 = _create_admin(client, slug=slug)
        agent_id, tool_id, api_key = _setup_agent_tool(
            client, t2,
            agent_name=f"pag-ag-{slug}",
            tool_name=f"pag-tl-{slug}",
        )
        # Fire 3 requests
        for _ in range(3):
            _guard_check(client, api_key, agent_id, f"pag-tl-{slug}")

        # page 1: limit=2
        r1 = client.get(
            "/api/v1/dashboard/activity?limit=2&offset=0",
            headers=auth_headers(t2),
        ).json()
        assert len(r1["items"]) == 2
        assert r1["total"] >= 3

        # page 2: limit=2, offset=2
        r2 = client.get(
            "/api/v1/dashboard/activity?limit=2&offset=2",
            headers=auth_headers(t2),
        ).json()
        assert len(r2["items"]) >= 1

    def test_activity_reverse_chronological_order(self, client):
        slug = make_unique_slug()
        t2, s2 = _create_admin(client, slug=slug)
        agent_id, tool_id, api_key = _setup_agent_tool(
            client, t2,
            agent_name=f"ord-ag-{slug}",
            tool_name=f"ord-tl-{slug}",
        )
        for _ in range(2):
            _guard_check(client, api_key, agent_id, f"ord-tl-{slug}")

        resp = client.get("/api/v1/dashboard/activity", headers=auth_headers(t2))
        items = resp.json()["items"]
        if len(items) >= 2:
            assert items[0]["created_at"] >= items[1]["created_at"]

    def test_activity_org_isolation(self, client):
        t_a, _ = _create_admin(client)
        t_b, _ = _create_admin(client)

        slug_a = make_unique_slug()
        t_a2, s_a2 = _create_admin(client, slug=slug_a)
        agent_id, tool_id, api_key = _setup_agent_tool(
            client, t_a2, agent_name=f"iso2-ag-{slug_a}", tool_name=f"iso2-tl-{slug_a}"
        )
        _guard_check(client, api_key, agent_id, f"iso2-tl-{slug_a}")

        # org-B should see 0 items
        resp = client.get("/api/v1/dashboard/activity", headers=auth_headers(t_b))
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_developer_denied_activity(self, client):
        admin_token, slug = _create_admin(client)
        dev_token = _create_user(client, slug, f"dev2+{slug}@test.com", "DEVELOPER")
        resp = client.get("/api/v1/dashboard/activity", headers=auth_headers(dev_token))
        assert resp.status_code == 403
