"""Part 1 Item 1: CRITICAL-risk Override Proof Script.

Proves that tools with risk level 'CRITICAL' (e.g. delete_database) are DENIED
by AgentGuard's policy engine EVEN WHEN an explicit permission grant exists.

Compares:
  - Result A (Unpermitted): DENY due to missing tool permission.
  - Result B (Permitted):   DENY due to CRITICAL risk policy rule.
"""
import os
import sys
import json
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from agentguard import AgentGuard, AgentGuardDenied
from app.core.database import SessionLocal
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.tool import Tool

API_BASE_URL = "http://localhost:8000/api/v1"
ORG_SLUG = "agentguard-demo"

def run_critical_override_proof():
    # 1. Login as ADMIN
    print("[1/5] Logging in as Admin...")
    r_auth = httpx.post(f"{API_BASE_URL}/auth/login", json={
        "email": "admin@agentguard-demo.local",
        "password": "DemoAdmin1!"
    })
    assert r_auth.status_code == 200
    token = r_auth.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    # 2. Get FinanceAgent and delete_database Tool IDs
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
        if not org:
            from app.core.seed import seed
            seed(db, org_slug=ORG_SLUG)
            org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
        agent = db.query(Agent).filter(Agent.organization_id == org.id, Agent.name == "FinanceAgent").first()
        tool = db.query(Tool).filter(Tool.organization_id == org.id, Tool.name == "delete_database").first()
        assert org and agent and tool
        agent_id = str(agent.id)
        tool_id = str(tool.id)
    finally:
        db.close()

    # 3. Step A: Call delete_database BEFORE granting permission (Result A)
    print("\n--- Result A: Calling delete_database WITHOUT permission grant ---")
    with open(os.path.join(PROJECT_ROOT, "docs", "demo-recording", "demo_env.json")) as f:
        demo_env = json.load(f)
    
    sdk_client = AgentGuard(
        api_key=demo_env["api_key"],
        base_url=API_BASE_URL,
        agent_id=agent_id,
    )

    result_a = None
    try:
        sdk_client.guard(tool="delete_database", parameters={"target": "prod_db"})
    except AgentGuardDenied as exc:
        result_a = {
            "guarantee": "Permission Check Enforcement (Missing Permission)",
            "tool": "delete_database",
            "decision": "DENY",
            "request_id": exc.request_id,
            "reason": exc.reason,
            "permission_granted_at_time_of_call": False
        }
        print(f"Result A Decision: DENY | Request ID: {exc.request_id} | Reason: {exc.reason}")

    # 4. Explicitly grant FinanceAgent permission for delete_database via POST /permissions
    print("\n[4/5] Explicitly granting permission for delete_database via POST /permissions...")
    r_grant = httpx.post(
        f"{API_BASE_URL}/permissions",
        json={"agent_id": agent_id, "tool_id": tool_id, "is_allowed": True},
        headers=admin_headers
    )
    assert r_grant.status_code == 200, f"Grant failed: {r_grant.text}"
    print(f"Permission Granted: agent_id={agent_id}, tool_id={tool_id}, is_allowed=True")

    # 5. Step B: Call delete_database AFTER granting permission (Result B)
    print("\n--- Result B: Calling delete_database WITH explicit permission grant ---")
    result_b = None
    try:
        sdk_client.guard(tool="delete_database", parameters={"target": "prod_db"})
    except AgentGuardDenied as exc:
        result_b = {
            "guarantee": "CRITICAL Risk Policy Enforcement (Permission Override Guarantee)",
            "tool": "delete_database",
            "decision": "DENY",
            "request_id": exc.request_id,
            "reason": exc.reason,
            "permission_granted_at_time_of_call": True
        }
        print(f"Result B Decision: DENY | Request ID: {exc.request_id} | Reason: {exc.reason}")

    assert result_b is not None
    assert "CRITICAL" in result_b["reason"], f"Expected 'CRITICAL' in reason, got: {result_b['reason']}"

    output = {
        "result_a_unpermitted": result_a,
        "result_b_permitted_critical_override": result_b
    }
    
    with open(os.path.join(PROJECT_ROOT, "docs", "demo-recording", "critical_denial_proof.json"), "w") as f:
        json.dump(output, f, indent=2)
        
    print("\n[SUCCESS] CRITICAL risk override successfully proven & saved to docs/demo-recording/critical_denial_proof.json")

if __name__ == "__main__":
    run_critical_override_proof()
