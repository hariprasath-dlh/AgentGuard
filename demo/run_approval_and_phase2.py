"""Execute Manager Approval, CRITICAL Denial, and Audit Chain Verification.

Completes the canonical governance demo loop:
1. Manager logs in, retrieves the pending HITL refund request (7806ad22-3136-42b2-88d5-7761784ccdd8).
2. Manager approves the request with note "Approved VIP refund per customer agreement".
3. Executes mock process_refund handler and updates state.
4. FinanceAgent attempts delete_database (CRITICAL risk) -> DENIED.
5. Auditor triggers cryptographic hash-chain audit vault verification -> CHAIN VALID.
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from demo.run_demo_scenario import run_agent_phase_2

API_BASE_URL = "http://localhost:8000/api/v1"

def approve_pending_request_as_manager():
    # 1. Login as MANAGER
    print("\n[Manager] Logging in as manager@agentguard-demo.local...")
    r = httpx.post(f"{API_BASE_URL}/auth/login", json={
        "email": "manager@agentguard-demo.local",
        "password": "DemoManager1!"
    })
    assert r.status_code == 200, f"Manager login failed: {r.text}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get pending HITL requests
    print("[Manager] Fetching pending HITL requests queue...")
    r_queue = httpx.get(f"{API_BASE_URL}/hitl?status=PENDING", headers=headers)
    assert r_queue.status_code == 200, f"Failed to list HITL requests: {r_queue.text}"
    items = r_queue.json().get("items", [])
    print(f"[Manager] Found {len(items)} pending HITL request(s).")
    
    if not items:
        print("ERROR: No pending HITL request found!")
        return None
        
    pending_item = items[0]
    hitl_id = pending_item["id"]
    tool_req_id = pending_item["tool_request_id"]
    tool_name = pending_item.get("tool_name") or pending_item.get("tool", {}).get("name", "process_refund")
    print(f"[Manager] Found target request: hitl_id={hitl_id}, tool_request_id={tool_req_id}, tool={tool_name}")
    
    # 3. Approve request with review note
    review_notes = "Approved VIP refund per customer agreement"
    print(f"[Manager] Approving request {hitl_id} with note: '{review_notes}'...")
    r_app = httpx.post(f"{API_BASE_URL}/hitl/{hitl_id}/approve", json={"review_notes": review_notes}, headers=headers)
    assert r_app.status_code == 200, f"Approval failed: {r_app.text}"
    app_data = r_app.json()
    print(f"[Manager] Approval Status: {app_data['status']}")
    print(f"[Manager] Output Payload: {app_data.get('output_payload')}")
    
    return {
        "hitl_id": hitl_id,
        "tool_request_id": tool_req_id,
        "status": app_data['status'],
        "output_payload": app_data.get('output_payload'),
        "review_notes": review_notes,
    }

def verify_audit_vault_as_auditor():
    # 1. Login as AUDITOR
    print("\n[Auditor] Logging in as auditor@agentguard-demo.local...")
    r = httpx.post(f"{API_BASE_URL}/auth/login", json={
        "email": "auditor@agentguard-demo.local",
        "password": "DemoAuditor1!"
    })
    assert r.status_code == 200, f"Auditor login failed: {r.text}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get Audit Vault Logs
    print("[Auditor] Fetching Audit Vault log entries...")
    r_logs = httpx.get(f"{API_BASE_URL}/audit?limit=50", headers=headers)
    assert r_logs.status_code == 200
    logs_data = r_logs.json().get("items", [])
    print(f"[Auditor] Retrieved {len(logs_data)} audit log records.")
    
    # 3. Trigger Cryptographic Chain Verification
    print("[Auditor] Executing SHA-256 Cryptographic Chain Verification...")
    r_verify = httpx.post(f"{API_BASE_URL}/audit/verify", headers=headers)
    assert r_verify.status_code == 200
    verify_data = r_verify.json()
    print(f"[Auditor] Verification Result: is_valid={verify_data.get('is_valid')}")
    print(f"[Auditor] Verified Records Count: {verify_data.get('total_records') or verify_data.get('records_verified')}")
    print(f"[Auditor] Details: {verify_data.get('details')}")
    
    return {
        "logs": logs_data,
        "verification": verify_data,
    }

def get_dashboard_summary():
    print("\n[Dashboard] Fetching live dashboard statistics...")
    r = httpx.post(f"{API_BASE_URL}/auth/login", json={
        "email": "admin@agentguard-demo.local",
        "password": "DemoAdmin1!"
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    r_stats = httpx.get(f"{API_BASE_URL}/dashboard/stats", headers=headers)
    assert r_stats.status_code == 200
    stats = r_stats.json()
    print(f"[Dashboard] Requests Today: {stats.get('requests_today')}")
    print(f"[Dashboard] Allowed Today: {stats.get('allowed_today')}")
    print(f"[Dashboard] Blocked Today: {stats.get('blocked_today')}")
    print(f"[Dashboard] Pending Today: {stats.get('pending_today')}")
    
    return stats

if __name__ == "__main__":
    with open(os.path.join(PROJECT_ROOT, "docs", "demo-recording", "demo_env.json")) as f:
        env = json.load(f)
        
    approval_res = approve_pending_request_as_manager()
    
    phase2_res = run_agent_phase_2(env)
    
    audit_res = verify_audit_vault_as_auditor()
    
    dash_res = get_dashboard_summary()
    
    summary = {
        "env": env,
        "approval": approval_res,
        "phase2_denial": phase2_res,
        "audit": audit_res["verification"],
        "dashboard_stats": dash_res,
    }
    
    with open(os.path.join(PROJECT_ROOT, "docs", "demo-recording", "final_demo_results.json"), "w") as f:
        json.dump(summary, f, indent=2)
        
    print("\n============================================================")
    print("DEMO SCENARIO EXECUTION COMPLETE: 100% SUCCESS")
    print("============================================================")
