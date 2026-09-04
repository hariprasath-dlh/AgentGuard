"""Phase 4 Agents + Tools Registry API tests.

Tests are organised by feature:
  - Agent CRUD & API key provisioning
  - Agent soft-delete semantics & uniqueness
  - Tool CRUD & retirement (no DELETE endpoint)
  - Tool uniqueness & risk levels
  - Permission grant/revoke, upsert semantics & indexed lookup
  - Comprehensive RBAC matrix enforcement across all 5 roles
  - Organization isolation (cross-org read/write/delete rejected)
  - Seed script idempotency & correct 5 demo tools
"""
import uuid
import pytest

from app.core.seed import seed, DEMO_TOOLS
from app.models.agent import Agent
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.repositories.registry import PermissionRepository
from tests.conftest import register_user, login_user, auth_headers, make_unique_slug


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_org_with_users(client):
    """Creates an organization with users for each of the 5 roles:
    ADMIN, SECURITY, DEVELOPER, MANAGER, AUDITOR.
    Returns a dict mapping role -> auth token, plus org_slug.
    """
    slug = make_unique_slug()
    # First user registered in a new org becomes ADMIN
    register_user(client, f"admin@{slug}.io", slug=slug)
    admin_tok = login_user(client, f"admin@{slug}.io", slug=slug).json()["access_token"]

    tokens = {"ADMIN": admin_tok}
    for role in ["SECURITY", "DEVELOPER", "MANAGER", "AUDITOR"]:
        email = f"{role.lower()}@{slug}.io"
        reg_resp, _ = register_user(client, email, slug=slug, role=role)
        assert reg_resp.status_code == 201, f"Failed to register {role}: {reg_resp.json()}"
        login_resp = login_user(client, email, slug=slug)
        assert login_resp.status_code == 200, f"Failed to login {role}: {login_resp.json()}"
        tokens[role] = login_resp.json()["access_token"]

    return tokens, slug


# ===========================================================================
# 1. Agent Registry Tests
# ===========================================================================

class TestAgentRegistry:
    def test_create_agent_returns_api_key_once(self, client):
        tokens, _ = create_org_with_users(client)
        resp = client.post(
            "/api/v1/agents",
            json={"name": "test-agent-1", "description": "A test agent"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-agent-1"
        assert data["status"] == "ACTIVE"
        assert "api_key" in data
        assert data["api_key"].startswith("ag_agent_")
        assert "api_key_id" in data
        assert "api_key_prefix" in data

        agent_id = data["id"]
        # Subsequent GET must NOT return plaintext api_key
        get_resp = client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers(tokens["ADMIN"]))
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert "api_key" not in get_data
        assert get_data["id"] == agent_id

    def test_duplicate_agent_name_in_same_org_rejected(self, client):
        tokens, _ = create_org_with_users(client)
        resp1 = client.post(
            "/api/v1/agents",
            json={"name": "unique-agent"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/agents",
            json={"name": "unique-agent"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"]

    def test_same_agent_name_in_different_orgs_allowed(self, client):
        tokens1, _ = create_org_with_users(client)
        tokens2, _ = create_org_with_users(client)

        resp1 = client.post(
            "/api/v1/agents",
            json={"name": "shared-name-agent"},
            headers=auth_headers(tokens1["ADMIN"]),
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/agents",
            json={"name": "shared-name-agent"},
            headers=auth_headers(tokens2["ADMIN"]),
        )
        assert resp2.status_code == 201

    def test_list_agents_filters_by_org(self, client):
        tokens1, _ = create_org_with_users(client)
        tokens2, _ = create_org_with_users(client)

        client.post("/api/v1/agents", json={"name": "agent-org-1"}, headers=auth_headers(tokens1["ADMIN"]))
        client.post("/api/v1/agents", json={"name": "agent-org-2"}, headers=auth_headers(tokens2["ADMIN"]))

        list1 = client.get("/api/v1/agents", headers=auth_headers(tokens1["ADMIN"])).json()
        names1 = [a["name"] for a in list1]
        assert "agent-org-1" in names1
        assert "agent-org-2" not in names1

    def test_update_agent(self, client):
        tokens, _ = create_org_with_users(client)
        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "agent-to-update"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        agent_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"/api/v1/agents/{agent_id}",
            json={"name": "agent-renamed", "description": "new desc", "status": "SUSPENDED"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["name"] == "agent-renamed"
        assert data["description"] == "new desc"
        assert data["status"] == "SUSPENDED"

    def test_soft_delete_agent(self, client):
        tokens, _ = create_org_with_users(client)
        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "agent-to-delete"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        agent_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/agents/{agent_id}", headers=auth_headers(tokens["ADMIN"]))
        assert del_resp.status_code == 204

        # GET /agents/{id} returns 404 for deleted agent
        get_resp = client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers(tokens["ADMIN"]))
        assert get_resp.status_code == 404

        # Not listed in GET /agents
        list_resp = client.get("/api/v1/agents", headers=auth_headers(tokens["ADMIN"]))
        ids = [a["id"] for a in list_resp.json()]
        assert agent_id not in ids


# ===========================================================================
# 2. Tool Registry Tests
# ===========================================================================

class TestToolRegistry:
    def test_create_tool_with_risk_levels(self, client):
        tokens, _ = create_org_with_users(client)
        for risk in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            resp = client.post(
                "/api/v1/tools",
                json={
                    "name": f"tool-{risk.lower()}",
                    "description": f"{risk} risk tool",
                    "risk_level": risk,
                },
                headers=auth_headers(tokens["ADMIN"]),
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == f"tool-{risk.lower()}"
            assert data["risk_level"] == risk
            assert data["is_active"] is True

    def test_duplicate_tool_name_rejected_in_same_org(self, client):
        tokens, _ = create_org_with_users(client)
        resp1 = client.post(
            "/api/v1/tools",
            json={"name": "same-tool"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/tools",
            json={"name": "same-tool"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert resp2.status_code == 409

    def test_no_delete_tool_endpoint(self, client):
        tokens, _ = create_org_with_users(client)
        create_resp = client.post(
            "/api/v1/tools",
            json={"name": "no-delete-tool"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        tool_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/tools/{tool_id}", headers=auth_headers(tokens["ADMIN"]))
        assert del_resp.status_code == 405  # Method Not Allowed

    def test_retire_tool_via_is_active_false(self, client):
        tokens, _ = create_org_with_users(client)
        create_resp = client.post(
            "/api/v1/tools",
            json={"name": "retireable-tool"},
            headers=auth_headers(tokens["ADMIN"]),
        )
        tool_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"/api/v1/tools/{tool_id}",
            json={"is_active": False},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["is_active"] is False


# ===========================================================================
# 3. Permission Assignment Tests
# ===========================================================================

class TestPermissionAssignment:
    def test_grant_permission_and_get(self, client):
        tokens, _ = create_org_with_users(client)
        agent_id = client.post(
            "/api/v1/agents", json={"name": "perm-agent"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]
        tool_id = client.post(
            "/api/v1/tools", json={"name": "perm-tool"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]

        grant_resp = client.post(
            "/api/v1/permissions",
            json={"agent_id": agent_id, "tool_id": tool_id, "is_allowed": True},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert grant_resp.status_code == 200
        data = grant_resp.json()
        assert data["agent_id"] == agent_id
        assert data["tool_id"] == tool_id
        assert data["is_allowed"] is True

    def test_idempotent_grant_upsert(self, client):
        tokens, _ = create_org_with_users(client)
        agent_id = client.post(
            "/api/v1/agents", json={"name": "perm-agent-dup"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]
        tool_id = client.post(
            "/api/v1/tools", json={"name": "perm-tool-dup"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]

        # Grant 1
        resp1 = client.post(
            "/api/v1/permissions",
            json={"agent_id": agent_id, "tool_id": tool_id, "is_allowed": True},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert resp1.status_code == 200
        perm_id_1 = resp1.json()["id"]

        # Grant 2 (updates allowed to False, no 409, does not duplicate row)
        resp2 = client.post(
            "/api/v1/permissions",
            json={"agent_id": agent_id, "tool_id": tool_id, "is_allowed": False},
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == perm_id_1
        assert resp2.json()["is_allowed"] is False

        # Verify only 1 permission row exists
        list_resp = client.get(f"/api/v1/permissions/agents/{agent_id}", headers=auth_headers(tokens["ADMIN"]))
        assert len(list_resp.json()) == 1

    def test_revoke_permission(self, client):
        tokens, _ = create_org_with_users(client)
        agent_id = client.post(
            "/api/v1/agents", json={"name": "revoke-agent"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]
        tool_id = client.post(
            "/api/v1/tools", json={"name": "revoke-tool"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]

        client.post(
            "/api/v1/permissions",
            json={"agent_id": agent_id, "tool_id": tool_id},
            headers=auth_headers(tokens["ADMIN"]),
        )

        del_resp = client.delete(
            f"/api/v1/permissions/{agent_id}/{tool_id}",
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["revoked"] is True

        # Second revoke returns 404
        del_resp2 = client.delete(
            f"/api/v1/permissions/{agent_id}/{tool_id}",
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert del_resp2.status_code == 404

    def test_repository_lookup_pattern(self, client, db_session):
        """Verify the exact indexed lookup PermissionRepository.get(agent_id, tool_id)
        that the Phase 5 policy engine will call.
        """
        tokens, slug = create_org_with_users(client)
        agent_id = uuid.UUID(client.post(
            "/api/v1/agents", json={"name": "repo-agent"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"])
        tool_id = uuid.UUID(client.post(
            "/api/v1/tools", json={"name": "repo-tool"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"])

        grant_resp = client.post(
            "/api/v1/permissions",
            json={"agent_id": str(agent_id), "tool_id": str(tool_id), "is_allowed": True},
            headers=auth_headers(tokens["ADMIN"]),
        )
        org_id = uuid.UUID(grant_resp.json()["organization_id"])

        repo = PermissionRepository(db=db_session, organization_id=org_id)
        perm = repo.get(agent_id, tool_id)
        assert perm is not None
        assert perm.is_allowed is True


# ===========================================================================
# 4. RBAC Matrix Enforcement Tests
# ===========================================================================

class TestRBACMatrix:
    """Matrix:
    - Create agent: ADMIN, SECURITY, DEVELOPER (201); MANAGER, AUDITOR (403)
    - Update/delete agent: ADMIN, SECURITY (200/204); DEVELOPER, MANAGER, AUDITOR (403)
    - Create tool: ADMIN, SECURITY, DEVELOPER (201); MANAGER, AUDITOR (403)
    - Update tool: ADMIN, SECURITY (200); DEVELOPER, MANAGER, AUDITOR (403)
    - Grant/revoke permission: ADMIN, SECURITY (200); DEVELOPER, MANAGER, AUDITOR (403)
    - Read (agents, tools, permissions): All 5 roles (200)
    """

    def test_create_agent_rbac(self, client):
        tokens, _ = create_org_with_users(client)
        # Allowed: ADMIN, SECURITY, DEVELOPER
        for role in ["ADMIN", "SECURITY", "DEVELOPER"]:
            resp = client.post(
                "/api/v1/agents",
                json={"name": f"agent-by-{role.lower()}"},
                headers=auth_headers(tokens[role]),
            )
            assert resp.status_code == 201, f"{role} should be able to create agent"

        # Forbidden: MANAGER, AUDITOR
        for role in ["MANAGER", "AUDITOR"]:
            resp = client.post(
                "/api/v1/agents",
                json={"name": f"agent-by-{role.lower()}"},
                headers=auth_headers(tokens[role]),
            )
            assert resp.status_code == 403, f"{role} should be forbidden from creating agent"

    def test_update_and_delete_agent_rbac(self, client):
        tokens, _ = create_org_with_users(client)
        agent_id = client.post(
            "/api/v1/agents", json={"name": "rbac-agent"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]

        # Forbidden to update: DEVELOPER, MANAGER, AUDITOR
        for role in ["DEVELOPER", "MANAGER", "AUDITOR"]:
            resp = client.patch(
                f"/api/v1/agents/{agent_id}",
                json={"description": f"updated by {role}"},
                headers=auth_headers(tokens[role]),
            )
            assert resp.status_code == 403, f"{role} should be forbidden from updating agent"

            resp_del = client.delete(
                f"/api/v1/agents/{agent_id}",
                headers=auth_headers(tokens[role]),
            )
            assert resp_del.status_code == 403, f"{role} should be forbidden from deleting agent"

        # Allowed to update: SECURITY
        sec_resp = client.patch(
            f"/api/v1/agents/{agent_id}",
            json={"description": "updated by security"},
            headers=auth_headers(tokens["SECURITY"]),
        )
        assert sec_resp.status_code == 200

        # Allowed to delete: ADMIN
        del_resp = client.delete(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert del_resp.status_code == 204

    def test_create_tool_rbac(self, client):
        tokens, _ = create_org_with_users(client)
        # Allowed: ADMIN, SECURITY, DEVELOPER
        for role in ["ADMIN", "SECURITY", "DEVELOPER"]:
            resp = client.post(
                "/api/v1/tools",
                json={"name": f"tool-by-{role.lower()}"},
                headers=auth_headers(tokens[role]),
            )
            assert resp.status_code == 201, f"{role} should be able to create tool"

        # Forbidden: MANAGER, AUDITOR
        for role in ["MANAGER", "AUDITOR"]:
            resp = client.post(
                "/api/v1/tools",
                json={"name": f"tool-by-{role.lower()}"},
                headers=auth_headers(tokens[role]),
            )
            assert resp.status_code == 403, f"{role} should be forbidden from creating tool"

    def test_update_tool_rbac(self, client):
        tokens, _ = create_org_with_users(client)
        tool_id = client.post(
            "/api/v1/tools", json={"name": "rbac-tool"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]

        # Forbidden: DEVELOPER, MANAGER, AUDITOR
        for role in ["DEVELOPER", "MANAGER", "AUDITOR"]:
            resp = client.patch(
                f"/api/v1/tools/{tool_id}",
                json={"description": f"updated by {role}"},
                headers=auth_headers(tokens[role]),
            )
            assert resp.status_code == 403, f"{role} should be forbidden from updating tool"

        # Allowed: SECURITY
        sec_resp = client.patch(
            f"/api/v1/tools/{tool_id}",
            json={"description": "updated by security"},
            headers=auth_headers(tokens["SECURITY"]),
        )
        assert sec_resp.status_code == 200

    def test_permission_grant_and_revoke_rbac(self, client):
        tokens, _ = create_org_with_users(client)
        agent_id = client.post(
            "/api/v1/agents", json={"name": "perm-rbac-agent"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]
        tool_id = client.post(
            "/api/v1/tools", json={"name": "perm-rbac-tool"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]

        # Forbidden: DEVELOPER, MANAGER, AUDITOR
        for role in ["DEVELOPER", "MANAGER", "AUDITOR"]:
            grant_resp = client.post(
                "/api/v1/permissions",
                json={"agent_id": agent_id, "tool_id": tool_id},
                headers=auth_headers(tokens[role]),
            )
            assert grant_resp.status_code == 403, f"{role} should not grant permissions"

            del_resp = client.delete(
                f"/api/v1/permissions/{agent_id}/{tool_id}",
                headers=auth_headers(tokens[role]),
            )
            assert del_resp.status_code == 403, f"{role} should not revoke permissions"

        # Allowed: SECURITY
        grant_resp = client.post(
            "/api/v1/permissions",
            json={"agent_id": agent_id, "tool_id": tool_id},
            headers=auth_headers(tokens["SECURITY"]),
        )
        assert grant_resp.status_code == 200

        # Allowed: ADMIN
        del_resp = client.delete(
            f"/api/v1/permissions/{agent_id}/{tool_id}",
            headers=auth_headers(tokens["ADMIN"]),
        )
        assert del_resp.status_code == 200

    def test_read_endpoints_accessible_to_all_roles(self, client):
        tokens, _ = create_org_with_users(client)
        # Seed an agent, tool, and permission
        agent_id = client.post(
            "/api/v1/agents", json={"name": "read-agent"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]
        tool_id = client.post(
            "/api/v1/tools", json={"name": "read-tool"}, headers=auth_headers(tokens["ADMIN"])
        ).json()["id"]
        client.post(
            "/api/v1/permissions",
            json={"agent_id": agent_id, "tool_id": tool_id},
            headers=auth_headers(tokens["ADMIN"]),
        )

        for role, token in tokens.items():
            assert client.get("/api/v1/agents", headers=auth_headers(token)).status_code == 200
            assert client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers(token)).status_code == 200
            assert client.get("/api/v1/tools", headers=auth_headers(token)).status_code == 200
            assert client.get(f"/api/v1/tools/{tool_id}", headers=auth_headers(token)).status_code == 200
            assert client.get("/api/v1/permissions", headers=auth_headers(token)).status_code == 200
            assert client.get(f"/api/v1/permissions/agents/{agent_id}", headers=auth_headers(token)).status_code == 200
            assert client.get(f"/api/v1/permissions/tools/{tool_id}", headers=auth_headers(token)).status_code == 200


# ===========================================================================
# 5. Organization Isolation Tests
# ===========================================================================

class TestOrgIsolation:
    def test_cross_org_agent_access_denied(self, client):
        tokens1, _ = create_org_with_users(client)
        tokens2, _ = create_org_with_users(client)

        agent_id = client.post(
            "/api/v1/agents", json={"name": "org1-agent"}, headers=auth_headers(tokens1["ADMIN"])
        ).json()["id"]

        # Org2 cannot read
        assert client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers(tokens2["ADMIN"])).status_code == 404
        # Org2 cannot update
        assert client.patch(
            f"/api/v1/agents/{agent_id}", json={"name": "hacked"}, headers=auth_headers(tokens2["ADMIN"])
        ).status_code == 404
        # Org2 cannot delete
        assert client.delete(f"/api/v1/agents/{agent_id}", headers=auth_headers(tokens2["ADMIN"])).status_code == 404

    def test_cross_org_tool_access_denied(self, client):
        tokens1, _ = create_org_with_users(client)
        tokens2, _ = create_org_with_users(client)

        tool_id = client.post(
            "/api/v1/tools", json={"name": "org1-tool"}, headers=auth_headers(tokens1["ADMIN"])
        ).json()["id"]

        assert client.get(f"/api/v1/tools/{tool_id}", headers=auth_headers(tokens2["ADMIN"])).status_code == 404
        assert client.patch(
            f"/api/v1/tools/{tool_id}", json={"name": "hacked"}, headers=auth_headers(tokens2["ADMIN"])
        ).status_code == 404

    def test_cross_org_permission_assignment_rejected(self, client):
        tokens1, _ = create_org_with_users(client)
        tokens2, _ = create_org_with_users(client)

        agent1_id = client.post(
            "/api/v1/agents", json={"name": "agent1"}, headers=auth_headers(tokens1["ADMIN"])
        ).json()["id"]
        tool1_id = client.post(
            "/api/v1/tools", json={"name": "tool1"}, headers=auth_headers(tokens1["ADMIN"])
        ).json()["id"]

        # Org2 tries to grant permission referencing Org1's agent or tool -> 404
        resp = client.post(
            "/api/v1/permissions",
            json={"agent_id": agent1_id, "tool_id": tool1_id},
            headers=auth_headers(tokens2["ADMIN"]),
        )
        assert resp.status_code == 404


# ===========================================================================
# 6. Seed Script Tests
# ===========================================================================

class TestSeedScript:
    def test_seed_produces_exact_five_tools_and_is_idempotent(self, db_session):
        slug = f"seed-test-{uuid.uuid4().hex[:6]}"

        # Run 1: seeds demo org, admin, and 5 demo tools
        res1 = seed(db_session, org_slug=slug)
        assert res1["org_created"] is True
        assert res1["tools_created"] == 5
        assert res1["tools_existing"] == 0

        # Verify exactly 5 tools created with exact names and risk levels
        expected = {t["name"]: t["risk_level"] for t in DEMO_TOOLS}
        tools = db_session.query(Tool).filter(Tool.organization.has(slug=slug)).all()
        assert len(tools) == 5
        for t in tools:
            assert t.name in expected
            assert t.risk_level == expected[t.name]
            assert t.is_active is True

        # Run 2: idempotent — no new tools created
        res2 = seed(db_session, org_slug=slug)
        assert res2["org_created"] is False
        assert res2["tools_created"] == 0
        assert res2["tools_existing"] == 5

        # Tool count still exactly 5
        tools_after = db_session.query(Tool).filter(Tool.organization.has(slug=slug)).all()
        assert len(tools_after) == 5
