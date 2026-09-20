"""
Phase 18 Performance Benchmark Seeder.

Creates 4 isolated organizations, each with:
  - 1 ADMIN user
  - 1 ACTIVE agent (FinanceAgent)
  - The 5 demo tools (seeded via app.core.seed)
  - 1 active API key for the agent

Prints a JSON object with org slugs and API keys for k6 consumption.
Run from backend/ directory with DATABASE_URL set.

Usage:
    python ../docs/performance/seed_perf.py
"""
import json
import os
import sys

# Ensure backend/ is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: registers all models on Base
from app.core.database import Base
from app.core.seed import seed
from app.models.agent import Agent
from app.models.api_key import APIKey
from app.models.budget import Budget
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.security.api_key import generate_api_key

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

results = []
NUM_ORGS = 4

try:
    for i in range(NUM_ORGS):
        slug = f"perf-org-{i}"

        # Idempotent: skip if org already exists
        org = db.query(Organization).filter_by(slug=slug).first()
        if not org:
            org = Organization(name=f"PerfOrg {i}", slug=slug)
            db.add(org)
            db.flush()

        # Seed the 5 demo tools + policies for this org
        seed(db, org_slug=slug)

        # Agent
        agent = db.query(Agent).filter_by(
            organization_id=org.id, name="PerfAgent"
        ).first()
        if not agent:
            agent = Agent(
                organization_id=org.id,
                name="PerfAgent",
                description="Load test agent",
                status="ACTIVE",
            )
            db.add(agent)
            db.flush()

        # Permissions for PerfAgent on all tools in this org
        tools = db.query(Tool).filter_by(organization_id=org.id).all()
        for t in tools:
            perm = db.query(AgentToolPermission).filter_by(
                organization_id=org.id, agent_id=agent.id, tool_id=t.id
            ).first()
            if not perm:
                perm = AgentToolPermission(
                    organization_id=org.id,
                    agent_id=agent.id,
                    tool_id=t.id,
                    is_allowed=True,
                )
                db.add(perm)
        db.flush()

        # Generous budget for benchmark agent
        budget = db.query(Budget).filter_by(
            organization_id=org.id, agent_id=agent.id
        ).first()
        if not budget:
            budget = Budget(
                organization_id=org.id,
                agent_id=agent.id,
                max_requests_per_minute=100000,
                max_requests_per_day=500000,
                max_budget_per_session=100000.0,
                max_budget_per_day=500000.0,
            )
            db.add(budget)
            db.flush()

        # API key (always create fresh so we have the raw value)
        raw_key, prefix, key_hash = generate_api_key(prefix="ag_agent")
        api_key = APIKey(
            organization_id=org.id,
            agent_id=agent.id,
            name=f"PerfKey-{i}",
            key_prefix=prefix,
            key_hash=key_hash,
            is_active=True,
        )
        db.add(api_key)
        db.flush()

        results.append({
            "org_slug": slug,
            "org_id": str(org.id),
            "agent_id": str(agent.id),
            "api_key": raw_key,
        })

    # Also seed a dedicated RateLimitAgent (cap 50 req/min) and BudgetAgent (cap $1.00/session) in org-0
    org0 = db.query(Organization).filter_by(slug="perf-org-0").first()
    if org0:
        # Rate-limited agent
        rl_agent = db.query(Agent).filter_by(organization_id=org0.id, name="RateLimitTestAgent").first()
        if not rl_agent:
            rl_agent = Agent(organization_id=org0.id, name="RateLimitTestAgent", status="ACTIVE")
            db.add(rl_agent)
            db.flush()
        
        for t in db.query(Tool).filter_by(organization_id=org0.id).all():
            if not db.query(AgentToolPermission).filter_by(organization_id=org0.id, agent_id=rl_agent.id, tool_id=t.id).first():
                db.add(AgentToolPermission(organization_id=org0.id, agent_id=rl_agent.id, tool_id=t.id, is_allowed=True))
        
        rl_budget = db.query(Budget).filter_by(organization_id=org0.id, agent_id=rl_agent.id).first()
        if not rl_budget:
            rl_budget = Budget(organization_id=org0.id, agent_id=rl_agent.id, max_requests_per_minute=200, max_requests_per_day=1000)
            db.add(rl_budget)
        else:
            rl_budget.max_requests_per_minute = 200
        
        raw_key_rl, prefix_rl, hash_rl = generate_api_key(prefix="ag_agent")
        db.add(APIKey(organization_id=org0.id, agent_id=rl_agent.id, name="RLKey", key_prefix=prefix_rl, key_hash=hash_rl, is_active=True))

        # Budget-capped agent
        b_agent = db.query(Agent).filter_by(organization_id=org0.id, name="BudgetCappedTestAgent").first()
        if not b_agent:
            b_agent = Agent(organization_id=org0.id, name="BudgetCappedTestAgent", status="ACTIVE")
            db.add(b_agent)
            db.flush()

        for t in db.query(Tool).filter_by(organization_id=org0.id).all():
            if not db.query(AgentToolPermission).filter_by(organization_id=org0.id, agent_id=b_agent.id, tool_id=t.id).first():
                db.add(AgentToolPermission(organization_id=org0.id, agent_id=b_agent.id, tool_id=t.id, is_allowed=True))

        b_budget = db.query(Budget).filter_by(organization_id=org0.id, agent_id=b_agent.id).first()
        if not b_budget:
            b_budget = Budget(organization_id=org0.id, agent_id=b_agent.id, max_budget_per_session=0.50, max_budget_per_day=1.00)
            db.add(b_budget)
        else:
            b_budget.max_budget_per_session = 0.50
            b_budget.max_budget_per_day = 1.00

        raw_key_b, prefix_b, hash_b = generate_api_key(prefix="ag_agent")
        db.add(APIKey(organization_id=org0.id, agent_id=b_agent.id, name="BudgetCapKey", key_prefix=prefix_b, key_hash=hash_b, is_active=True))

        db.flush()
        with open(os.path.join(BASE_DIR, "special_keys.json"), "w") as f:
            json.dump({
                "rate_limit_agent_key": raw_key_rl,
                "rate_limit_agent_id": str(rl_agent.id),
                "budget_agent_key": raw_key_b,
                "budget_agent_id": str(b_agent.id),
            }, f, indent=2)

    db.commit()
    print(json.dumps(results, indent=2))
finally:
    db.close()
