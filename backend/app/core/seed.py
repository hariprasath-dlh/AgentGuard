"""Idempotent seed script for the AgentGuard demo scenario.

Creates the five named tools required by the Phase 4 demo and the demo
organization + admin user if they don't already exist.

Running this script twice leaves EXACTLY five demo tools, not ten.

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

# Ensure the backend package root is on the path when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.organization import Organization
from app.models.role import Role
from app.models.tool import Tool
from app.models.user import User
from app.security.password import hash_password

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo tool definitions (project.md § demo scenario)
# These are registry entries ONLY. No execution logic lives here.
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
DEMO_ADMIN_EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "admin@agentguard-demo.local")
DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "DemoAdmin1!")


def seed(db: Session, org_slug: str = DEMO_ORG_SLUG) -> dict:
    """Run all seed operations. Returns a summary dict.

    Safe to call multiple times — all inserts are conditional on non-existence.
    """
    results = {
        "org_created": False,
        "admin_created": False,
        "tools_created": 0,
        "tools_existing": 0,
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
    # 2. Ensure ADMIN role exists for this org
    # ------------------------------------------------------------------
    admin_role = (
        db.query(Role)
        .filter(Role.organization_id == org.id, Role.name == "ADMIN")
        .first()
    )
    if not admin_role:
        admin_role = Role(organization_id=org.id, name="ADMIN")
        db.add(admin_role)
        db.flush()
        log.info("Created ADMIN role")

    # ------------------------------------------------------------------
    # 3. Ensure demo admin user exists
    # ------------------------------------------------------------------
    admin_user = (
        db.query(User)
        .filter(User.email == DEMO_ADMIN_EMAIL, User.organization_id == org.id)
        .first()
    )
    if not admin_user:
        admin_user = User(
            organization_id=org.id,
            email=DEMO_ADMIN_EMAIL,
            hashed_password=hash_password(DEMO_ADMIN_PASSWORD),
            full_name="Demo Administrator",
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin_user)
        db.flush()
        results["admin_created"] = True
        log.info(f"Created demo admin user: {DEMO_ADMIN_EMAIL}")
    else:
        log.info(f"Demo admin already exists: {DEMO_ADMIN_EMAIL}")

    # ------------------------------------------------------------------
    # 4. Seed the five demo tools (idempotent)
    # ------------------------------------------------------------------
    for tool_def in DEMO_TOOLS:
        existing = (
            db.query(Tool)
            .filter(Tool.organization_id == org.id, Tool.name == tool_def["name"])
            .first()
        )
        if existing:
            log.info(f"Tool already exists: {tool_def['name']} ({tool_def['risk_level']})")
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
            results["tools_created"] += 1
            log.info(f"Created tool: {tool_def['name']} ({tool_def['risk_level']})")

    db.flush()
    db.commit()

    log.info(
        f"Seed complete — tools created: {results['tools_created']}, "
        f"already existed: {results['tools_existing']}"
    )
    return results


def run_seed():
    db = SessionLocal()
    try:
        summary = seed(db)
        total_tools = summary["tools_created"] + summary["tools_existing"]
        assert total_tools == 5, f"Expected 5 demo tools, got {total_tools}"
        log.info(f"✓ Seed verified: exactly {total_tools} demo tools present")
    except Exception as e:
        log.error(f"Seed failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
