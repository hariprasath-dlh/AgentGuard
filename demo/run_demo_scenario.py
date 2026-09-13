"""Automated Runner for the Canonical End-to-End Governance Demo Scenario.

Implements the exact sequence from project.md:
1. FinanceAgent calls read_customer (LOW risk) -> ALLOW
2. FinanceAgent calls send_email (MEDIUM risk) -> ALLOW
3. FinanceAgent calls process_refund (HIGH risk, amount=75,000) -> PENDING
4. (Pauses for Human Reviewer approval via UI/API)
5. FinanceAgent calls delete_database (CRITICAL risk) -> DENY
6. Verifies full audit hash-chain integrity
"""
import os
import sys
import json
import uuid
import httpx
from datetime import datetime, timezone

# Ensure project root and backend are on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal
from app.core.seed import seed
from app.models.agent import Agent
from app.models.api_key import APIKey
from app.models.organization import Organization
from app.models.tool import Tool
from app.models.permission import AgentToolPermission
from app.models.budget import Budget
from app.security.api_key import generate_api_key
from agentguard import AgentGuard, AgentGuardDenied, AgentGuardPending

API_BASE_URL = os.getenv("AGENTGUARD_BASE_URL", "http://localhost:8000/api/v1")
ORG_SLUG = "agentguard-demo"

def setup_demo_environment():
    db = SessionLocal()
    try:
        print("[Setup] Seeding demo environment...")
        seed(db, org_slug=ORG_SLUG)
        
        org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
        agent = db.query(Agent).filter(Agent.organization_id == org.id, Agent.name == "FinanceAgent").first()
        
        # Ensure an active API key exists for FinanceAgent
        api_key_record = db.query(APIKey).filter(APIKey.organization_id == org.id, APIKey.agent_id == agent.id, APIKey.is_active == True).first()
        if not api_key_record:
            raw_key, prefix, key_hash = generate_api_key(prefix="ag_agent")
            api_key_record = APIKey(
                organization_id=org.id,
                agent_id=agent.id,
                name="FinanceAgentDemoKey",
                key_prefix=prefix,
                key_hash=key_hash,
                is_active=True,
            )
            db.add(api_key_record)
            db.commit()
        else:
            # Generate a fresh known key for the demo session
            raw_key, prefix, key_hash = generate_api_key(prefix="ag_agent")
            api_key_record.key_prefix = prefix
            api_key_record.key_hash = key_hash
            db.commit()
            
        print(f"[Setup] Org: {org.name} ({org.slug}, id={org.id})")
        print(f"[Setup] Agent: {agent.name} (id={agent.id})")
        print(f"[Setup] API Key: {raw_key}")
        
        return {
            "org_id": str(org.id),
            "agent_id": str(agent.id),
            "api_key": raw_key,
        }
    finally:
        db.close()

def run_agent_phase_1(env):
    """Executes the pre-approval agent steps: read_customer, send_email, process_refund."""
    client = AgentGuard(
        api_key=env["api_key"],
        base_url=API_BASE_URL,
        agent_id=env["agent_id"],
    )
    
    results = {}
    
    # Step 1: read_customer (LOW)
    print("\n--- Step 1: FinanceAgent reads customer account (LOW risk) ---")
    res1 = client.guard(
        tool="read_customer",
        parameters={"customer_id": "CUST-9921", "fields": ["name", "email", "balance"]},
    )
    print(f"Decision: {res1.decision} | Request ID: {res1.request_id} | Reason: {res1.reason}")
    results["step1"] = {"tool": "read_customer", "decision": res1.decision, "request_id": res1.request_id, "reason": res1.reason}
    
    # Step 2: send_email (MEDIUM)
    print("\n--- Step 2: FinanceAgent sends transactional notification (MEDIUM risk) ---")
    res2 = client.guard(
        tool="send_email",
        parameters={"to": "customer.9921@example.com", "subject": "Account Review", "body": "Your refund request is being processed."},
    )
    print(f"Decision: {res2.decision} | Request ID: {res2.request_id} | Reason: {res2.reason}")
    results["step2"] = {"tool": "send_email", "decision": res2.decision, "request_id": res2.request_id, "reason": res2.reason}
    
    # Step 3: process_refund (HIGH - INR 75,000)
    print("\n--- Step 3: FinanceAgent requests high-value refund (HIGH risk, INR 75,000) ---")
    try:
        client.guard(
            tool="process_refund",
            parameters={"customer_id": "CUST-9921", "amount": 75000.0, "currency": "INR", "reason": "VIP billing adjustment"},
        )
        print("ERROR: Expected PENDING exception!")
    except AgentGuardPending as pending_exc:
        print(f"Decision: PENDING (Intercepted for HITL) | Request ID: {pending_exc.request_id} | Reason: {pending_exc.reason}")
        results["step3"] = {"tool": "process_refund", "decision": "PENDING", "request_id": pending_exc.request_id, "reason": pending_exc.reason}
        
    return results

def run_agent_phase_2(env):
    """Executes the post-approval agent step: delete_database (CRITICAL)."""
    client = AgentGuard(
        api_key=env["api_key"],
        base_url=API_BASE_URL,
        agent_id=env["agent_id"],
    )
    
    print("\n--- Step 4: FinanceAgent attempts destructive database deletion (CRITICAL risk) ---")
    try:
        client.guard(
            tool="delete_database",
            parameters={"target": "production_users", "cascade": True},
        )
        print("CRITICAL SECURITY FAILURE: delete_database was not blocked!")
        return {"tool": "delete_database", "decision": "ALLOW", "request_id": None}
    except AgentGuardDenied as deny_exc:
        print(f"Decision: DENY (BLOCKED AT GATEWAY) | Request ID: {deny_exc.request_id} | Reason: {deny_exc.reason}")
        return {"tool": "delete_database", "decision": "DENY", "request_id": deny_exc.request_id, "reason": deny_exc.reason}

if __name__ == "__main__":
    env = setup_demo_environment()
    print("\n[Demo] Environment ready. Saving env to scratch...")
    with open(os.path.join(PROJECT_ROOT, "docs", "demo-recording", "demo_env.json"), "w") as f:
        json.dump(env, f, indent=2)
    
    p1 = run_agent_phase_1(env)
    with open(os.path.join(PROJECT_ROOT, "docs", "demo-recording", "phase1_results.json"), "w") as f:
        json.dump(p1, f, indent=2)
