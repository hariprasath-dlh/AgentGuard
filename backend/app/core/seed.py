"""Idempotent seed script for the AgentGuard demo scenario.

Creates the five named tools required by the Phase 4 demo, the demo
organization, five demo role users (ADMIN, SECURITY, AUDITOR, MANAGER, DEVELOPER),
a demo FinanceAgent with default budget and permissions, and historical
telemetry spread over recent days for dashboard and HITL verification.

Running this script twice is safe and idempotent.

Usage:
    python -m app.core.seed
    # or, specifying a custom org slug:
    ORG_SLUG=my-demo-org python -m app.core.seed

SAFETY: No code in this file executes real destructive operations.
Tools are registry rows only — there is no execution logic here.
"""
import os
import sys
import logging
import uuid
from datetime import datetime, timedelta, timezone

# Ensure the backend package root is on the path when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.agent import Agent
from app.models.audit_log import AuditLog
from app.models.budget import Budget
from app.models.hitl_request import HITLRequest
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.role import Role
from app.models.tool import Tool
from app.models.tool_request import ToolRequest
from app.models.user import User
from app.security.password import hash_password
from app.services.audit_vault import record_audit_log

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo tool definitions (project.md § demo scenario)
# ---------------------------------------------------------------------------
DEMO_TOOLS = [
    {
        "name": "read_customer",
        "description": "Read customer profile and account information (mock)",
        "risk_level": "LOW",
    },
    {
        "name": "create_ticket",
        "description": "Create a support ticket (mock)",
        "risk_level": "LOW",
    },
    {
        "name": "send_email",
        "description": "Send a transactional email to a customer (mock)",
        "risk_level": "MEDIUM",
    },
    {
        "name": "process_refund",
        "description": "Process a payment refund — requires human approval for HIGH risk (mock)",
        "risk_level": "HIGH",
    },
    {
        "name": "delete_database",
        "description": "Delete database records — CRITICAL risk, always requires HITL (mock)",
        "risk_level": "CRITICAL",
    },
]

DEMO_ORG_SLUG = os.getenv("ORG_SLUG", "agentguard-demo")
DEMO_ORG_NAME = "AgentGuard Demo Organization"

# ---------------------------------------------------------------------------
# Demo role users with fixed development-only credentials
# ---------------------------------------------------------------------------
DEMO_USERS = [
    {
        "role": "ADMIN",
        "email": os.getenv("DEMO_ADMIN_EMAIL", "admin@agentguard-demo.local"),
        "password": os.getenv("DEMO_ADMIN_PASSWORD", "DemoAdmin1!"),
        "full_name": "Demo Administrator",
    },
    {
        "role": "SECURITY",
        "email": "security@agentguard-demo.local",
        "password": "DemoSecurity1!",
        "full_name": "Demo Security Officer",
    },
    {
        "role": "AUDITOR",
        "email": "auditor@agentguard-demo.local",
        "password": "DemoAuditor1!",
        "full_name": "Demo Compliance Auditor",
    },
    {
        "role": "MANAGER",
        "email": "manager@agentguard-demo.local",
        "password": "DemoManager1!",
        "full_name": "Demo Operations Manager",
    },
    {
        "role": "DEVELOPER",
        "email": "developer@agentguard-demo.local",
        "password": "DemoDeveloper1!",
        "full_name": "Demo Agent Developer",
    },
]


def seed(db: Session, org_slug: str = DEMO_ORG_SLUG) -> dict:
    """Run all seed operations. Returns a summary dict.

    Safe to call multiple times — all inserts are conditional on non-existence.
    """
    results = {
        "org_created": False,
        "users_created": 0,
        "users_existing": 0,
        "tools_created": 0,
        "tools_existing": 0,
        "agent_created": False,
        "permissions_created": 0,
        "requests_seeded": 0,
    }

    # ------------------------------------------------------------------
    # 1. Ensure demo organization exists
    # ------------------------------------------------------------------
    org = db.query(Organization).filter(Organization.slug == org_slug).first()
    if not org:
        org = Organization(name=DEMO_ORG_NAME, slug=org_slug)
        db.add(org)
        db.flush()
        results["org_created"] = True
        log.info(f"Created organization: {org_slug} (id={org.id})")
    else:
        log.info(f"Organization already exists: {org_slug} (id={org.id})")

    # ------------------------------------------------------------------
    # 2. Ensure all five roles exist for this org
    # ------------------------------------------------------------------
    roles_by_name = {}
    for user_def in DEMO_USERS:
        role_name = user_def["role"]
        role = (
            db.query(Role)
            .filter(Role.organization_id == org.id, Role.name == role_name)
            .first()
        )
        if not role:
            role = Role(organization_id=org.id, name=role_name)
            db.add(role)
            db.flush()
            log.info(f"Created role: {role_name}")
        roles_by_name[role_name] = role

    # ------------------------------------------------------------------
    # 3. Ensure demo users exist for each role
    # ------------------------------------------------------------------
    for user_def in DEMO_USERS:
        existing_user = (
            db.query(User)
            .filter(User.email == user_def["email"], User.organization_id == org.id)
            .first()
        )
        if not existing_user:
            user = User(
                organization_id=org.id,
                email=user_def["email"],
                hashed_password=hash_password(user_def["password"]),
                full_name=user_def["full_name"],
                role_id=roles_by_name[user_def["role"]].id,
                is_active=True,
            )
            db.add(user)
            db.flush()
            results["users_created"] += 1
            log.info(f"Created demo user: {user_def['email']} ({user_def['role']})")
        else:
            results["users_existing"] += 1
            log.info(f"Demo user already exists: {user_def['email']}")

    # ------------------------------------------------------------------
    # 4. Seed the five demo tools (idempotent)
    # ------------------------------------------------------------------
    tools_by_name = {}
    for tool_def in DEMO_TOOLS:
        existing = (
            db.query(Tool)
            .filter(Tool.organization_id == org.id, Tool.name == tool_def["name"])
            .first()
        )
        if existing:
            tools_by_name[tool_def["name"]] = existing
            results["tools_existing"] += 1
        else:
            tool = Tool(
                organization_id=org.id,
                name=tool_def["name"],
                description=tool_def["description"],
                risk_level=tool_def["risk_level"],
                is_active=True,
            )
            db.add(tool)
            db.flush()
            tools_by_name[tool_def["name"]] = tool
            results["tools_created"] += 1
            log.info(f"Created tool: {tool_def['name']} ({tool_def['risk_level']})")

    # ------------------------------------------------------------------
    # 5. Ensure demo FinanceAgent exists with default budget
    # ------------------------------------------------------------------
    agent = (
        db.query(Agent)
        .filter(Agent.organization_id == org.id, Agent.name == "FinanceAgent")
        .first()
    )
    if not agent:
        agent = Agent(
            organization_id=org.id,
            name="FinanceAgent",
            description="Autonomous customer service & finance support agent",
            status="ACTIVE",
        )
        db.add(agent)
        db.flush()
        results["agent_created"] = True
        log.info(f"Created agent: {agent.name}")

    # Ensure agent budget row exists
    budget = (
        db.query(Budget)
        .filter(Budget.organization_id == org.id, Budget.agent_id == agent.id)
        .first()
    )
    if not budget:
        budget = Budget(
            organization_id=org.id,
            agent_id=agent.id,
            max_requests_per_minute=100,
            max_requests_per_day=5000,
            max_budget_per_session=100.0,
            max_budget_per_day=500.0,
        )
        db.add(budget)
        db.flush()
        log.info(f"Provisioned budget for agent: {agent.name}")

    # ------------------------------------------------------------------
    # 6. Ensure permissions exist for FinanceAgent
    # ------------------------------------------------------------------
    allowed_tools = ["read_customer", "create_ticket", "send_email", "process_refund"]
    for tool_name in allowed_tools:
        if tool_name in tools_by_name:
            t = tools_by_name[tool_name]
            perm = (
                db.query(AgentToolPermission)
                .filter(
                    AgentToolPermission.organization_id == org.id,
                    AgentToolPermission.agent_id == agent.id,
                    AgentToolPermission.tool_id == t.id,
                )
                .first()
            )
            if not perm:
                perm = AgentToolPermission(
                    organization_id=org.id,
                    agent_id=agent.id,
                    tool_id=t.id,
                    is_allowed=True,
                )
                db.add(perm)
                db.flush()
                results["permissions_created"] += 1

    # ------------------------------------------------------------------
    # 7. Seed historical requests and a real PENDING HITL request
    # ------------------------------------------------------------------
    existing_requests_count = (
        db.query(ToolRequest)
        .filter(ToolRequest.organization_id == org.id)
        .count()
    )
    if existing_requests_count == 0:
        now = datetime.now(timezone.utc)
        # Seed events across days 5, 4, 3, 2, 1, and today
        event_specs = [
            # Day -4
            {"tool": "read_customer", "days_ago": 4, "decision": "ALLOW", "reason": "All governance checks passed"},
            {"tool": "create_ticket", "days_ago": 4, "decision": "ALLOW", "reason": "All governance checks passed"},
            # Day -3
            {"tool": "read_customer", "days_ago": 3, "decision": "ALLOW", "reason": "All governance checks passed"},
            {"tool": "delete_database", "days_ago": 3, "decision": "DENY", "reason": "Tool has risk level 'CRITICAL', which is denied by policy"},
            # Day -2
            {"tool": "send_email", "days_ago": 2, "decision": "ALLOW", "reason": "All governance checks passed"},
            {"tool": "read_customer", "days_ago": 2, "decision": "ALLOW", "reason": "All governance checks passed"},
            # Day -1
            {"tool": "read_customer", "days_ago": 1, "decision": "ALLOW", "reason": "All governance checks passed"},
            {"tool": "process_refund", "days_ago": 1, "decision": "ALLOW", "reason": "Approved by human reviewer"},
            # Today
            {"tool": "read_customer", "days_ago": 0, "decision": "ALLOW", "reason": "All governance checks passed"},
            {"tool": "send_email", "days_ago": 0, "decision": "ALLOW", "reason": "All governance checks passed"},
            {"tool": "process_refund", "days_ago": 0, "decision": "PENDING", "reason": "Tool 'process_refund' has risk level 'HIGH', which requires human approval (HITL)."},
        ]

        for spec in event_specs:
            t = tools_by_name.get(spec["tool"])
            if not t:
                continue
            event_time = now - timedelta(days=spec["days_ago"], minutes=30)
            req = ToolRequest(
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=t.id,
                decision=spec["decision"],
                reason=spec["reason"],
                input_payload={
                    "tool_name": t.name,
                    "action": "execute",
                    "parameters": {"customer_id": "cust_4821", "amount": 250.0},
                    "estimated_cost": 0.05,
                    "estimated_tokens": 120,
                },
                created_at=event_time,
                updated_at=event_time,
            )
            db.add(req)
            db.flush()

            # Record in cryptographic audit vault
            audit_log = record_audit_log(
                db=db,
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=t.id,
                event_type="TOOL_REQUEST_EVALUATED",
                decision=spec["decision"],
                payload={
                    "request_id": str(req.id),
                    "agent_id": str(agent.id),
                    "agent_name": agent.name,
                    "tool_id": str(t.id),
                    "tool_name": t.name,
                    "action": "execute",
                    "decision": spec["decision"],
                    "reason": spec["reason"],
                },
                request_id=req.id,
                tool_name=t.name,
            )
            req.audit_log_id = audit_log.id

            # If PENDING, create real HITLRequest
            if spec["decision"] == "PENDING":
                hitl = HITLRequest(
                    organization_id=org.id,
                    tool_request_id=req.id,
                    status="PENDING",
                    expires_at=now + timedelta(hours=24),
                    created_at=event_time,
                    updated_at=event_time,
                )
                db.add(hitl)
                db.flush()

            results["requests_seeded"] += 1
        log.info(f"Seeded {results['requests_seeded']} historical tool requests across past 5 days")

    # Ensure there is always at least one PENDING HITL request for demo review
    pending_hitl_count = (
        db.query(HITLRequest)
        .filter(HITLRequest.organization_id == org.id, HITLRequest.status == "PENDING")
        .count()
    )
    if pending_hitl_count == 0:
        now = datetime.now(timezone.utc)
        t = tools_by_name.get("process_refund")
        if t and agent:
            req = ToolRequest(
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=t.id,
                decision="PENDING",
                reason="Tool 'process_refund' has risk level 'HIGH', which requires human approval (HITL).",
                input_payload={
                    "tool_name": t.name,
                    "action": "execute",
                    "parameters": {"customer_id": "cust_9921", "amount": 499.0, "reason": "Customer cancellation request"},
                    "estimated_cost": 0.10,
                    "estimated_tokens": 150,
                },
                created_at=now,
                updated_at=now,
            )
            db.add(req)
            db.flush()

            audit_log = record_audit_log(
                db=db,
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=t.id,
                event_type="TOOL_REQUEST_EVALUATED",
                decision="PENDING",
                payload={
                    "request_id": str(req.id),
                    "agent_id": str(agent.id),
                    "agent_name": agent.name,
                    "tool_id": str(t.id),
                    "tool_name": t.name,
                    "action": "execute",
                    "decision": "PENDING",
                    "reason": "Tool 'process_refund' has risk level 'HIGH', which requires human approval (HITL).",
                },
                request_id=req.id,
                tool_name=t.name,
            )
            req.audit_log_id = audit_log.id

            hitl = HITLRequest(
                organization_id=org.id,
                tool_request_id=req.id,
                status="PENDING",
                expires_at=now + timedelta(hours=24),
                created_at=now,
                updated_at=now,
            )
            db.add(hitl)
            db.flush()
            results["requests_seeded"] += 1
            log.info("Provisioned a PENDING HITL request for process_refund")

    db.commit()

    log.info(
        f"Seed complete — users created: {results['users_created']}, "
        f"tools created: {results['tools_created']}, "
        f"requests seeded: {results['requests_seeded']}"
    )
    return results


def run_seed():
    db = SessionLocal()
    try:
        summary = seed(db)
        log.info(f"✓ Seed verified successfully: {summary}")
    except Exception as e:
        log.error(f"Seed failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
