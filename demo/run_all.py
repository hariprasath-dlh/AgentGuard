"""Phase 11: Framework-Agnostic Governance Demonstration Runner.

Orchestrates three diverse agent architectures (Custom Python Agent,
LangChain-style Tool Agent, and Simulated FSM Agent) against a live
AgentGuard backend to prove framework-agnostic runtime governance.

Features:
  1. Idempotent provisioning reusing the Phase 4 seed pattern.
  2. Automated live backend connectivity and health verification.
  3. Execution of Demo 1 (Custom OOP Agent), Demo 2 (LangChain Agent), and Demo 3 (Simulated FSM).
  4. Cross-demo consistency assertions: mathematically proves that all three
     agents produce identical decisions and reasons for identical tool calls.
  5. Verifiable audit trail logging with genuine server-generated request UUIDs.
"""
import os
import sys
import time
import uuid
import logging
import subprocess
from datetime import datetime, timezone
from typing import Any, Optional

# Ensure project root and backend are on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import httpx
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.seed import seed
from app.models.agent import Agent
from app.models.api_key import APIKey
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.security.api_key import hash_api_key

from agentguard import AgentGuard
from demo.agents.custom_agent import run_custom_agent
from demo.agents.langchain_agent import run_langchain_agent
from demo.agents.simulated_agent import run_simulated_agent

DEMO_ORG_SLUG = "agentguard-demo"
DEMO_AGENT_NAME = "FrameworkDemoAgent"
DEMO_RAW_KEY = "ag_live_demo_framework_key_778899"
SERVER_BASE_URL = os.getenv("AGENTGUARD_BASE_URL", "http://127.0.0.1:8000")
API_V1_URL = f"{SERVER_BASE_URL}/api/v1"


class TeeStream:
    """Tees stdout/stderr to both console and a log file."""

    def __init__(self, filepath: str, original_stream):
        self.file = open(filepath, "w", encoding="utf-8")
        self.original = original_stream

    def write(self, data):
        try:
            self.original.write(data)
        except UnicodeEncodeError:
            self.original.write(data.encode("ascii", "replace").decode("ascii"))
        self.file.write(data)
        self.original.flush()
        self.file.flush()

    def flush(self):
        self.original.flush()
        self.file.flush()

    def close(self):
        self.file.close()


def provision_demo_environment(db: Session, org_slug: str = DEMO_ORG_SLUG) -> dict[str, Any]:
    """Idempotently provisions the organization, tools, demo agent, permissions, and API key.

    Reuses Phase 4's seed pattern. Safe to run repeatedly without creating duplicates.
    """
    print(f"\n[Provisioning] Verifying demo organization and seeded tools (slug={org_slug})...")
    seed_summary = seed(db, org_slug=org_slug)

    org = db.query(Organization).filter(Organization.slug == org_slug).first()
    assert org is not None, f"Organization {org_slug} must exist"

    # 1. Ensure Demo Agent exists
    agent = (
        db.query(Agent)
        .filter(Agent.organization_id == org.id, Agent.name == DEMO_AGENT_NAME)
        .first()
    )
    agent_created = False
    if not agent:
        agent = Agent(
            organization_id=org.id,
            name=DEMO_AGENT_NAME,
            description="Autonomous multi-framework governance verification agent",
            status="ACTIVE",
        )
        db.add(agent)
        db.flush()
        agent_created = True
        print(f"[Provisioning] Created demo agent: {DEMO_AGENT_NAME} (id={agent.id})")
    else:
        print(f"[Provisioning] Demo agent already exists: {DEMO_AGENT_NAME} (id={agent.id})")

    # 2. Ensure permissions exist for all 5 demo tools
    tools = db.query(Tool).filter(Tool.organization_id == org.id).all()
    perms_created = 0
    perms_existing = 0
    for tool in tools:
        perm = (
            db.query(AgentToolPermission)
            .filter(
                AgentToolPermission.agent_id == agent.id,
                AgentToolPermission.tool_id == tool.id,
            )
            .first()
        )
        if not perm:
            perm = AgentToolPermission(
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=tool.id,
                is_allowed=True,
            )
            db.add(perm)
            perms_created += 1
        else:
            perms_existing += 1
    db.flush()
    print(f"[Provisioning] Permissions verified (created: {perms_created}, existing: {perms_existing})")

    # 3. Ensure deterministic demo API key exists
    key_hash = hash_api_key(DEMO_RAW_KEY)
    key_prefix = DEMO_RAW_KEY[:12]
    api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
    key_created = False
    if not api_key:
        api_key = APIKey(
            organization_id=org.id,
            agent_id=agent.id,
            name="DemoFrameworkKey",
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=True,
        )
        db.add(api_key)
        key_created = True
        print(f"[Provisioning] Created demo API key with prefix: {key_prefix}...")
    else:
        if not api_key.is_active:
            api_key.is_active = True
        print(f"[Provisioning] Demo API key already exists with prefix: {key_prefix}...")

    db.commit()

    return {
        "org_id": str(org.id),
        "agent_id": str(agent.id),
        "agent_created": agent_created,
        "key_created": key_created,
        "perms_created": perms_created,
        "perms_existing": perms_existing,
        "raw_key": DEMO_RAW_KEY,
    }


def wait_for_server(base_url: str, timeout: float = 12.0) -> bool:
    """Check if the backend server is responding to health checks."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def run_cross_demo_consistency_check(
    demo1_results: list[dict[str, Any]],
    demo2_results: list[dict[str, Any]],
    demo3_results: list[dict[str, Any]],
) -> None:
    """Asserts that all three agents produced identical governance decisions and reason strings.

    Only the server-generated request_id UUIDs must differ.
    """
    print("\n" + "=" * 80)
    print("CROSS-DEMO CONSISTENCY VERIFICATION")
    print("=" * 80)
    print("Verifying that Custom, LangChain, and FSM agents received identical decisions\n"
          "and reasons for the exact same tool calls through the AgentGuard SDK contract.\n")

    assert len(demo1_results) == len(demo2_results) == len(demo3_results) == 3, (
        f"Expected 3 results per agent, got {len(demo1_results)}, {len(demo2_results)}, {len(demo3_results)}"
    )

    all_request_ids = set()

    for idx in range(3):
        r1 = demo1_results[idx]
        r2 = demo2_results[idx]
        r3 = demo3_results[idx]

        tool_name = r1["tool"]
        print(f"Tool [{idx+1}/3]: '{tool_name}'")
        print(f"  Demo 1 (Custom OOP Agent): decision={r1['decision']}, executed={r1['executed']}, req_id={r1['request_id']}")
        print(f"  Demo 2 (LangChain Agent):  decision={r2['decision']}, executed={r2['executed']}, req_id={r2['request_id']}")
        print(f"  Demo 3 (Simulated FSM):    decision={r3['decision']}, executed={r3['executed']}, req_id={r3['request_id']}")

        # 1. Decision must be identical across all 3
        assert r1["decision"] == r2["decision"] == r3["decision"], (
            f"Decision mismatch for {tool_name}: Demo1={r1['decision']}, Demo2={r2['decision']}, Demo3={r3['decision']}"
        )

        # 2. Reason must be identical across all 3
        assert r1["reason"] == r2["reason"] == r3["reason"], (
            f"Reason mismatch for {tool_name}:\nDemo1: {r1['reason']}\nDemo2: {r2['reason']}\nDemo3: {r3['reason']}"
        )
        print(f"  Unified Reason: '{r1['reason']}'")

        # 3. Execution outcome must match
        assert r1["executed"] == r2["executed"] == r3["executed"], (
            f"Execution mismatch for {tool_name}: Demo1={r1['executed']}, Demo2={r2['executed']}, Demo3={r3['executed']}"
        )

        # 4. Request IDs must be distinct, non-empty UUIDs
        req_ids = [r1["request_id"], r2["request_id"], r3["request_id"]]
        for rid in req_ids:
            assert rid is not None and len(rid) > 0, f"Empty request_id for {tool_name}"
            # Validate UUID format
            uuid.UUID(rid)
            all_request_ids.add(rid)

        # Ensure all 3 request_ids for this step are distinct
        assert len(set(req_ids)) == 3, f"Duplicate request_id detected across agents for {tool_name}: {req_ids}"
        print(f"  [PASS] Consistency check PASSED for tool '{tool_name}'\n")

    # All 9 request IDs across the 3 demos must be globally unique
    assert len(all_request_ids) == 9, f"Expected 9 unique request IDs, got {len(all_request_ids)}"
    print("[PASS] All 9 server-generated request UUIDs are distinct and authentic.")
    print("[PASS] CROSS-DEMO CONSISTENCY PROOF COMPLETE: Contract identical across all 3 agent architectures.")


def main():
    log_path = os.path.join(PROJECT_ROOT, "demo", "demo_output.log")
    tee = TeeStream(log_path, sys.stdout)
    sys.stdout = tee
    sys.stderr = tee

    server_process = None
    db = SessionLocal()

    try:
        print("=" * 80)
        print("AGENTGUARD: FRAMEWORK-AGNOSTIC RUNTIME GOVERNANCE DEMONSTRATION")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print(f"Python Executable: {sys.executable}")
        print("=" * 80)

        # 1. Idempotent Provisioning
        prov = provision_demo_environment(db, org_slug=DEMO_ORG_SLUG)

        # 2. Check or start live FastAPI server
        if not wait_for_server(SERVER_BASE_URL, timeout=1.0):
            print(f"\n[Server] Backend not responding at {SERVER_BASE_URL}. Starting live FastAPI server...")
            server_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=BACKEND_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if not wait_for_server(SERVER_BASE_URL, timeout=15.0):
                raise RuntimeError(f"Backend failed to start and respond at {SERVER_BASE_URL} within 15 seconds")
            print(f"[Server] Live FastAPI backend successfully started at {SERVER_BASE_URL}")
        else:
            print(f"\n[Server] Live FastAPI backend is actively running at {SERVER_BASE_URL}")

        # 3. Instantiate AgentGuard SDK Client
        client = AgentGuard(
            api_key=prov["raw_key"],
            base_url=API_V1_URL,
            timeout=10.0,
            max_retries=2,
        )

        # 4. Run Demo 1: Custom Python Agent
        demo1_results = run_custom_agent(client=client, agent_id=prov["agent_id"])

        # 5. Run Demo 2: LangChain-Style Tool Agent
        demo2_results = run_langchain_agent(client=client, agent_id=prov["agent_id"])

        # 6. Run Demo 3: Simulated Agent (Event-Driven State Machine)
        demo3_results = run_simulated_agent(client=client, agent_id=prov["agent_id"])

        # 7. Execute Cross-Demo Consistency Check
        run_cross_demo_consistency_check(demo1_results, demo2_results, demo3_results)

        print("\n" + "=" * 80)
        print("PHASE 11 DEMONSTRATION COMPLETED SUCCESSFULLY")
        print(f"Output recorded to: {log_path}")
        print("=" * 80)

    finally:
        db.close()
        if server_process is not None:
            print("\n[Server] Terminating background server process...")
            server_process.terminate()
            server_process.wait()
        sys.stdout = tee.original
        sys.stderr = tee.original
        tee.close()


if __name__ == "__main__":
    main()
