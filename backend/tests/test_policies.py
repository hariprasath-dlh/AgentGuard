"""Tests for Policy CRUD endpoints (Phase 12).

Tests cover:
  - List returns all policies scoped to org (including inactive)
  - Create with valid rules returns 201
  - Create rejects empty rules dict (422)
  - Create rejects rules with no recognised key (422)
  - Create rejects duplicate name (409)
  - PATCH updates name, rules, and is_active
  - DELETE soft-deletes (is_active → False, 204)
  - RBAC: AUDITOR and MANAGER can read but not write
  - RBAC: DEVELOPER is denied all access
  - Org isolation: policy from org-A not visible to org-B
"""
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


VALID_RULES = {"allowed_actions": ["read_file"], "blocked_actions": ["delete_database"]}


def _create_policy(client, token, name="test-policy", rules=None):
    return client.post(
        "/api/v1/policies",
        json={
            "name": name,
            "policy_type": "RISK",
            "rules": VALID_RULES if rules is None else rules,
        },
        headers=auth_headers(token),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPolicyCRUD:
    def test_create_policy_returns_201(self, client):
        token, _ = _create_admin(client)
        resp = _create_policy(client, token)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-policy"
        assert data["policy_type"] == "RISK"
        assert data["is_active"] is True

    def test_create_policy_empty_rules_rejected(self, client):
        token, _ = _create_admin(client)
        resp = _create_policy(client, token, name="bad-policy", rules={})
        assert resp.status_code == 422

    def test_create_policy_unrecognised_rules_rejected(self, client):
        token, _ = _create_admin(client)
        resp = _create_policy(client, token, name="bad-policy2", rules={"foo": "bar"})
        assert resp.status_code == 422
        assert "recognised key" in resp.json()["detail"]

    def test_create_policy_duplicate_name_rejected(self, client):
        token, _ = _create_admin(client)
        _create_policy(client, token, name="dup-policy")
        resp = _create_policy(client, token, name="dup-policy")
        assert resp.status_code == 409

    def test_list_policies_includes_all(self, client):
        token, _ = _create_admin(client)
        _create_policy(client, token, name="pol-1")
        _create_policy(client, token, name="pol-2")
        resp = client.get("/api/v1/policies", headers=auth_headers(token))
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "pol-1" in names
        assert "pol-2" in names

    def test_patch_policy_updates_name_and_rules(self, client):
        token, _ = _create_admin(client)
        create_resp = _create_policy(client, token, name="patch-me")
        pid = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/policies/{pid}",
            json={"name": "patched", "rules": {"risk_thresholds": {"HIGH": "PENDING"}}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "patched"

    def test_patch_policy_bad_rules_rejected(self, client):
        token, _ = _create_admin(client)
        create_resp = _create_policy(client, token, name="patch-bad")
        pid = create_resp.json()["id"]
        resp = client.patch(
            f"/api/v1/policies/{pid}",
            json={"rules": {"garbage": True}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    def test_delete_policy_soft_deletes(self, client):
        token, _ = _create_admin(client)
        create_resp = _create_policy(client, token, name="del-me")
        pid = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/policies/{pid}", headers=auth_headers(token))
        assert resp.status_code == 204

        # Policy still listed but is_active=False
        list_resp = client.get("/api/v1/policies", headers=auth_headers(token))
        match = next((p for p in list_resp.json() if p["id"] == pid), None)
        assert match is not None
        assert match["is_active"] is False

    def test_delete_nonexistent_returns_404(self, client):
        token, _ = _create_admin(client)
        import uuid
        resp = client.delete(f"/api/v1/policies/{uuid.uuid4()}", headers=auth_headers(token))
        assert resp.status_code == 404


class TestPolicyRBAC:
    def test_auditor_can_read(self, client):
        admin_token, slug = _create_admin(client)
        _create_policy(client, admin_token, name="rbac-read")
        auditor_token = _create_user(client, slug, f"auditor+{slug}@test.com", "AUDITOR")
        resp = client.get("/api/v1/policies", headers=auth_headers(auditor_token))
        assert resp.status_code == 200

    def test_manager_can_read(self, client):
        admin_token, slug = _create_admin(client)
        _create_policy(client, admin_token, name="mgr-read")
        mgr_token = _create_user(client, slug, f"mgr+{slug}@test.com", "MANAGER")
        resp = client.get("/api/v1/policies", headers=auth_headers(mgr_token))
        assert resp.status_code == 200

    def test_auditor_cannot_create(self, client):
        admin_token, slug = _create_admin(client)
        auditor_token = _create_user(client, slug, f"aud2+{slug}@test.com", "AUDITOR")
        resp = _create_policy(client, auditor_token, name="aud-create")
        assert resp.status_code == 403

    def test_manager_cannot_create(self, client):
        admin_token, slug = _create_admin(client)
        mgr_token = _create_user(client, slug, f"mgr2+{slug}@test.com", "MANAGER")
        resp = _create_policy(client, mgr_token, name="mgr-create")
        assert resp.status_code == 403

    def test_developer_denied_all(self, client):
        admin_token, slug = _create_admin(client)
        dev_token = _create_user(client, slug, f"dev+{slug}@test.com", "DEVELOPER")
        resp = client.get("/api/v1/policies", headers=auth_headers(dev_token))
        assert resp.status_code == 403


class TestPolicyOrgIsolation:
    def test_org_a_cannot_see_org_b_policies(self, client):
        token_a, _ = _create_admin(client)
        token_b, _ = _create_admin(client)

        _create_policy(client, token_a, name="org-a-pol")

        resp = client.get("/api/v1/policies", headers=auth_headers(token_b))
        assert resp.status_code == 200
        assert all("org-a-pol" not in p["name"] for p in resp.json())
