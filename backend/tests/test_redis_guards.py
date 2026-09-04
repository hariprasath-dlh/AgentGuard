"""Integration tests for Redis Rate Limiter and Cost Guard (Phase 6).

Tested against a real Redis instance on localhost:6379:
  - Sliding-window rate limiter blocks after Nth request in window
  - Rate limit unblocks once the window slides forward
  - Budget exhaustion matches the worked $1.00 / $0.98 / $0.05 example exactly
  - Token-based rate limiting
  - Two different agents' counters are completely isolated
  - Redis connection failure fails safe (fail-closed: denies by default)
"""
from decimal import Decimal
import time
import uuid
import pytest
import redis
from sqlalchemy.orm import Session

from app.core.redis import get_redis_client
from app.models.agent import Agent
from app.models.budget import Budget
from app.models.organization import Organization
from app.models.permission import AgentToolPermission
from app.models.tool import Tool
from app.schemas.policy import CallerIdentity, DecisionEnum, DecisionInput
from app.services.budget_guard import RedisBudgetChecker
from app.services.factory import create_policy_engine
from app.services.rate_limiter import RedisRateLimitChecker


@pytest.fixture
def redis_client():
    """Real Redis client fixture for integration testing."""
    client = get_redis_client()
    # Verify connection
    assert client.ping() is True
    yield client


@pytest.fixture
def test_setup(db_session: Session, redis_client: redis.Redis):
    """Sets up an org, two agents, a tool, and cleans up Redis keys."""
    org = Organization(name="Redis Test Org", slug=f"redis-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()

    agent1 = Agent(
        organization_id=org.id,
        name="FinanceAgent-1",
        description="First agent",
        status="ACTIVE",
    )
    agent2 = Agent(
        organization_id=org.id,
        name="FinanceAgent-2",
        description="Second agent",
        status="ACTIVE",
    )
    tool = Tool(
        organization_id=org.id,
        name="read_customer",
        description="Customer reader",
        risk_level="LOW",
        is_active=True,
    )
    db_session.add_all([agent1, agent2, tool])
    db_session.flush()

    # Permissions
    perm1 = AgentToolPermission(organization_id=org.id, agent_id=agent1.id, tool_id=tool.id, is_allowed=True)
    perm2 = AgentToolPermission(organization_id=org.id, agent_id=agent2.id, tool_id=tool.id, is_allowed=True)
    db_session.add_all([perm1, perm2])
    db_session.flush()

    # Clear any residual keys in Redis for both agents
    for a in [agent1, agent2]:
        RedisRateLimitChecker(redis_client).reset(a.id)
        RedisBudgetChecker(redis_client).reset(a.id)

    return {"org": org, "agent1": agent1, "agent2": agent2, "tool": tool}


def make_caller(agent: Agent) -> CallerIdentity:
    return CallerIdentity(
        caller_type="AGENT",
        caller_id=agent.id,
        organization_id=agent.organization_id,
        is_authenticated=True,
    )


# ===========================================================================
# 1. Rate Limiting Tests
# ===========================================================================

class TestRedisRateLimiter:
    def test_rate_limit_blocks_after_n_requests(self, db_session, redis_client, test_setup):
        """Rate limit blocks the request immediately after Nth request in window."""
        agent = test_setup["agent1"]
        tool = test_setup["tool"]

        # Configure agent with limit of 3 requests per minute
        budget = Budget(
            organization_id=test_setup["org"].id,
            agent_id=agent.id,
            max_requests_per_minute=3,
        )
        db_session.add(budget)
        db_session.flush()

        engine = create_policy_engine(db=db_session, redis_client=redis_client)
        caller = make_caller(agent)
        inp = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read")

        # Requests 1, 2, 3 must pass
        for i in range(3):
            out = engine.evaluate(inp, caller)
            assert out.decision == DecisionEnum.ALLOW, f"Request {i+1} failed: {out.reason}"
            assert out.checks["RATE_LIMIT"].status.value == "PASSED"

        # Request 4 must be BLOCKED
        out_blocked = engine.evaluate(inp, caller)
        assert out_blocked.decision == DecisionEnum.DENY
        assert "Rate limit exceeded" in out_blocked.reason
        assert out_blocked.checks["RATE_LIMIT"].status.value == "FAILED"

    def test_rate_limit_unblocks_when_window_slides(self, db_session, redis_client, test_setup):
        """Rate limit allows requests again once the sliding window rolls."""
        agent = test_setup["agent1"]
        tool = test_setup["tool"]

        # Use short 2-second window for this test
        rate_checker = RedisRateLimitChecker(
            redis_client=redis_client,
            default_requests_per_minute=2,
            window_seconds=1.5,
        )
        budget_checker = RedisBudgetChecker(redis_client=redis_client)
        from app.services.policy_engine import PolicyEngine
        engine = PolicyEngine(db=db_session, budget_checker=budget_checker, rate_limit_checker=rate_checker)

        caller = make_caller(agent)
        inp = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read")

        # 2 requests allowed
        assert engine.evaluate(inp, caller).decision == DecisionEnum.ALLOW
        assert engine.evaluate(inp, caller).decision == DecisionEnum.ALLOW

        # 3rd is blocked
        blocked = engine.evaluate(inp, caller)
        assert blocked.decision == DecisionEnum.DENY

        # Wait for the 1.5s window to roll
        time.sleep(1.6)

        # 4th request must be allowed again
        allowed_again = engine.evaluate(inp, caller)
        assert allowed_again.decision == DecisionEnum.ALLOW

    def test_token_rate_limiting(self, db_session, redis_client, test_setup):
        """Token rate limit blocks when tokens in window exceed threshold."""
        agent = test_setup["agent1"]
        tool = test_setup["tool"]

        rate_checker = RedisRateLimitChecker(
            redis_client=redis_client,
            default_requests_per_minute=100,
            default_tokens_per_minute=1000,
        )
        budget_checker = RedisBudgetChecker(redis_client=redis_client)
        from app.services.policy_engine import PolicyEngine
        engine = PolicyEngine(db=db_session, budget_checker=budget_checker, rate_limit_checker=rate_checker)

        caller = make_caller(agent)

        # 600 tokens -> passes
        inp1 = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read", estimated_tokens=600)
        assert engine.evaluate(inp1, caller).decision == DecisionEnum.ALLOW

        # Another 300 tokens (total 900 <= 1000) -> passes
        inp2 = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read", estimated_tokens=300)
        assert engine.evaluate(inp2, caller).decision == DecisionEnum.ALLOW

        # Another 200 tokens (total 1100 > 1000) -> blocked
        inp3 = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read", estimated_tokens=200)
        blocked = engine.evaluate(inp3, caller)
        assert blocked.decision == DecisionEnum.DENY
        assert "Token rate limit exceeded" in blocked.reason


# ===========================================================================
# 2. Budget Enforcement Tests
# ===========================================================================

class TestRedisBudgetGuard:
    def test_worked_example_exact_reproduction(self, db_session, redis_client, test_setup):
        """Reproduce project.md's worked example as a literal test case:
        An agent with a $1.00 budget, $0.98 already spent, and a new $0.05 request
        must be DENYed.
        """
        agent = test_setup["agent1"]
        tool = test_setup["tool"]

        # Budget of $1.00, $0.98 already spent
        budget = Budget(
            organization_id=test_setup["org"].id,
            agent_id=agent.id,
            max_budget_per_session=Decimal("1.00"),
            max_budget_per_day=Decimal("1.00"),
            current_spend=Decimal("0.98"),
        )
        db_session.add(budget)
        db_session.flush()

        # Explicitly set current session spend in Redis to $0.98
        budget_checker = RedisBudgetChecker(redis_client=redis_client)
        redis_client.set(budget_checker._session_cost_key(agent.id), "0.98")

        engine = create_policy_engine(db=db_session, redis_client=redis_client)
        caller = make_caller(agent)

        # New request for $0.05 (0.98 + 0.05 = 1.03 > 1.00)
        inp = DecisionInput(
            agent_id=agent.id,
            tool_name=tool.name,
            action="read",
            estimated_cost=0.05,
        )
        out = engine.evaluate(inp, caller)

        assert out.decision == DecisionEnum.DENY
        assert "budget limit exceeded" in out.reason.lower()
        assert "$0.98" in out.reason
        assert "$0.05" in out.reason
        assert "$1.00" in out.reason
        assert out.checks["BUDGET"].status.value == "FAILED"

    def test_budget_spend_accumulates_and_blocks(self, db_session, redis_client, test_setup):
        """Demonstrates that spend increments in Redis and eventually triggers budget cap."""
        agent = test_setup["agent1"]
        tool = test_setup["tool"]

        budget = Budget(
            organization_id=test_setup["org"].id,
            agent_id=agent.id,
            max_budget_per_session=Decimal("0.50"),
            current_spend=Decimal("0.0"),
        )
        db_session.add(budget)
        db_session.flush()

        engine = create_policy_engine(db=db_session, redis_client=redis_client)
        caller = make_caller(agent)

        # Request 1: $0.20 (spent: $0.20 <= $0.50) -> ALLOW
        inp1 = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read", estimated_cost=0.20)
        assert engine.evaluate(inp1, caller).decision == DecisionEnum.ALLOW

        # Request 2: $0.20 (spent: $0.40 <= $0.50) -> ALLOW
        inp2 = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read", estimated_cost=0.20)
        assert engine.evaluate(inp2, caller).decision == DecisionEnum.ALLOW

        # Request 3: $0.20 (spent: 0.40 + 0.20 = 0.60 > 0.50) -> DENY
        inp3 = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read", estimated_cost=0.20)
        blocked = engine.evaluate(inp3, caller)
        assert blocked.decision == DecisionEnum.DENY
        assert "budget limit exceeded" in blocked.reason.lower()


# ===========================================================================
# 3. Agent Isolation Tests
# ===========================================================================

class TestAgentIsolation:
    def test_two_agents_counters_never_interfere(self, db_session, redis_client, test_setup):
        """Agent 1 exhausting its rate limit or budget must NOT affect Agent 2."""
        agent1 = test_setup["agent1"]
        agent2 = test_setup["agent2"]
        tool = test_setup["tool"]

        # Agent 1 has limit of 2 req/min; Agent 2 has limit of 10 req/min
        b1 = Budget(organization_id=test_setup["org"].id, agent_id=agent1.id, max_requests_per_minute=2)
        b2 = Budget(organization_id=test_setup["org"].id, agent_id=agent2.id, max_requests_per_minute=10)
        db_session.add_all([b1, b2])
        db_session.flush()

        engine = create_policy_engine(db=db_session, redis_client=redis_client)

        caller1 = make_caller(agent1)
        caller2 = make_caller(agent2)

        inp1 = DecisionInput(agent_id=agent1.id, tool_name=tool.name, action="read")
        inp2 = DecisionInput(agent_id=agent2.id, tool_name=tool.name, action="read")

        # Exhaust Agent 1 limit (2 requests)
        assert engine.evaluate(inp1, caller1).decision == DecisionEnum.ALLOW
        assert engine.evaluate(inp1, caller1).decision == DecisionEnum.ALLOW
        assert engine.evaluate(inp1, caller1).decision == DecisionEnum.DENY  # Agent 1 blocked!

        # Agent 2 must STILL be allowed
        assert engine.evaluate(inp2, caller2).decision == DecisionEnum.ALLOW
        assert engine.evaluate(inp2, caller2).decision == DecisionEnum.ALLOW
        assert engine.evaluate(inp2, caller2).decision == DecisionEnum.ALLOW


# ===========================================================================
# 4. Fail-Closed Security Policy Tests
# ===========================================================================

class TestFailClosedSecurity:
    def test_redis_connection_failure_fails_closed(self, db_session, test_setup):
        """When Redis is unreachable, checkers fail-closed (DENY by default)."""
        agent = test_setup["agent1"]
        tool = test_setup["tool"]

        # Point client to a non-existent port
        dead_client = redis.Redis(host="localhost", port=6399, socket_timeout=0.1, socket_connect_timeout=0.1)

        engine = create_policy_engine(db=db_session, redis_client=dead_client)
        caller = make_caller(agent)
        inp = DecisionInput(agent_id=agent.id, tool_name=tool.name, action="read")

        out = engine.evaluate(inp, caller)
        assert out.decision == DecisionEnum.DENY
        assert "fail-closed policy" in out.reason.lower()
