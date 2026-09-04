"""Factory for creating fully wired PolicyEngine instances (Phase 6).

Injects the concrete Redis-backed budget and rate limit checkers into PolicyEngine.
"""
from typing import Optional
import redis
from sqlalchemy.orm import Session

from app.core.redis import get_redis_client
from app.services.budget_guard import RedisBudgetChecker
from app.services.policy_engine import PolicyEngine
from app.services.rate_limiter import RedisRateLimitChecker


def create_policy_engine(
    db: Session,
    redis_client: Optional[redis.Redis] = None,
) -> PolicyEngine:
    """Instantiate a PolicyEngine wired with real Redis-backed checkers.

    Can accept an explicit redis_client (e.g. for testing) or fall back to
    the shared application Redis client pool.
    """
    if redis_client is None:
        redis_client = get_redis_client()

    budget_checker = RedisBudgetChecker(redis_client=redis_client)
    rate_limit_checker = RedisRateLimitChecker(redis_client=redis_client)

    return PolicyEngine(
        db=db,
        budget_checker=budget_checker,
        rate_limit_checker=rate_limit_checker,
    )
