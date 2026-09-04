"""Redis-backed Cost and Budget Guard (Phase 6).

Implements BudgetChecker protocol from Phase 5.
Enforces SESSION_COST_LIMIT, DAILY_COST_LIMIT, and SESSION_TOKEN_LIMIT.
Uses PostgreSQL 'budgets' table as the source of truth for limits,
and Redis for ultra-low latency running total counters.

Security policy: Fail-closed. If Redis is unreachable, requests are denied by default.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
import uuid
from typing import Optional, Tuple
import redis
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.budget import Budget
from app.models.tool import Tool
from app.schemas.policy import DecisionInput

log = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 3600            # 1 hour of inactivity resets session
DAILY_TTL_SECONDS = 86400 * 2         # 2 days retention for daily keys
DEFAULT_SESSION_TOKEN_LIMIT = 500000  # Fallback session token cap


class RedisBudgetChecker:
    """Fast-path cost & token budget enforcement backed by Redis.

    Conforms to BudgetChecker protocol:
        (db: Session, input_data: DecisionInput, agent: Agent, tool: Tool) -> (bool, Optional[str])
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        session_ttl: int = SESSION_TTL_SECONDS,
        default_session_token_limit: int = DEFAULT_SESSION_TOKEN_LIMIT,
    ):
        self.redis = redis_client
        self.session_ttl = session_ttl
        self.default_session_token_limit = default_session_token_limit

    def _get_utc_date(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _session_cost_key(self, agent_id: uuid.UUID) -> str:
        return f"budget:session:cost:{agent_id}"

    def _daily_cost_key(self, agent_id: uuid.UUID, date_str: str) -> str:
        return f"budget:daily:cost:{agent_id}:{date_str}"

    def _session_token_key(self, agent_id: uuid.UUID) -> str:
        return f"budget:session:tokens:{agent_id}"

    def _daily_token_key(self, agent_id: uuid.UUID, date_str: str) -> str:
        return f"budget:daily:tokens:{agent_id}:{date_str}"

    def reset(self, agent_id: uuid.UUID) -> None:
        """Utility for test suites to clear running totals for an agent."""
        date_str = self._get_utc_date()
        try:
            self.redis.delete(
                self._session_cost_key(agent_id),
                self._daily_cost_key(agent_id, date_str),
                self._session_token_key(agent_id),
                self._daily_token_key(agent_id, date_str),
            )
        except Exception:
            pass

    def __call__(
        self,
        db: Session,
        input_data: DecisionInput,
        agent: Agent,
        tool: Tool,
    ) -> Tuple[bool, Optional[str]]:
        """Check whether proposed request exceeds session/daily cost or token limits.

        Returns (allowed: bool, reason: Optional[str]).
        """
        budget_row = (
            db.query(Budget)
            .filter(Budget.agent_id == agent.id)
            .first()
        )

        cost = float(input_data.estimated_cost or 0.0)
        tokens = int(input_data.estimated_tokens or 0)
        date_str = self._get_utc_date()

        sess_cost_key = self._session_cost_key(agent.id)
        day_cost_key = self._daily_cost_key(agent.id, date_str)
        sess_tok_key = self._session_token_key(agent.id)
        day_tok_key = self._daily_token_key(agent.id, date_str)

        try:
            # ---------------------------------------------------------------
            # 1. Fetch current spend totals from Redis (Fast Path)
            # ---------------------------------------------------------------
            pipe = self.redis.pipeline()
            pipe.get(sess_cost_key)
            pipe.get(day_cost_key)
            pipe.get(sess_tok_key)
            pipe.get(day_tok_key)
            res = pipe.execute()

            # Handle session spend initialization from DB if not yet in Redis
            raw_sess_cost = res[0]
            if raw_sess_cost is None:
                initial_cost = float(budget_row.current_spend) if budget_row and budget_row.current_spend else 0.0
                curr_sess_cost = initial_cost
                self.redis.set(sess_cost_key, str(initial_cost), ex=self.session_ttl)
            else:
                curr_sess_cost = float(raw_sess_cost)

            curr_day_cost = float(res[1]) if res[1] is not None else curr_sess_cost
            curr_sess_tokens = int(res[2]) if res[2] is not None else 0
            curr_day_tokens = int(res[3]) if res[3] is not None else 0

            # ---------------------------------------------------------------
            # 2. Check Session Cost Limit
            # ---------------------------------------------------------------
            if budget_row and budget_row.max_budget_per_session is not None:
                sess_limit = float(budget_row.max_budget_per_session)
                if round(curr_sess_cost + cost, 4) > round(sess_limit, 4):
                    return (
                        False,
                        f"Session budget limit exceeded: current spend ${curr_sess_cost:.2f} + "
                        f"estimated ${cost:.2f} exceeds limit of ${sess_limit:.2f}.",
                    )

            # ---------------------------------------------------------------
            # 3. Check Daily Cost Limit
            # ---------------------------------------------------------------
            if budget_row and budget_row.max_budget_per_day is not None:
                daily_limit = float(budget_row.max_budget_per_day)
                if round(curr_day_cost + cost, 4) > round(daily_limit, 4):
                    return (
                        False,
                        f"Daily budget limit exceeded: current spend ${curr_day_cost:.2f} + "
                        f"estimated ${cost:.2f} exceeds limit of ${daily_limit:.2f}.",
                    )

            # ---------------------------------------------------------------
            # 4. Check Session Token Limit
            # ---------------------------------------------------------------
            if tokens > 0 and curr_sess_tokens + tokens > self.default_session_token_limit:
                return (
                    False,
                    f"Session token limit exceeded: current {curr_sess_tokens} + "
                    f"estimated {tokens} exceeds limit of {self.default_session_token_limit} tokens.",
                )

            # ---------------------------------------------------------------
            # 5. Record spend in Redis and flush DB counters
            # ---------------------------------------------------------------
            pipe = self.redis.pipeline()
            if cost > 0:
                pipe.incrbyfloat(sess_cost_key, cost)
                pipe.expire(sess_cost_key, self.session_ttl)
                pipe.incrbyfloat(day_cost_key, cost)
                pipe.expire(day_cost_key, DAILY_TTL_SECONDS)

            if tokens > 0:
                pipe.incrby(sess_tok_key, tokens)
                pipe.expire(sess_tok_key, self.session_ttl)
                pipe.incrby(day_tok_key, tokens)
                pipe.expire(day_tok_key, DAILY_TTL_SECONDS)

            pipe.execute()

            # Synchronize DB row if present
            if budget_row and cost > 0:
                budget_row.current_spend = budget_row.current_spend + Decimal(str(cost))
                db.flush()

            return True, None

        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            # FAIL-CLOSED SECURITY POLICY
            log.error(f"Redis budget guard connection error: {e}")
            return False, "Budget check failed: Redis connection unavailable (fail-closed policy)."
