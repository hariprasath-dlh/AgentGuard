"""Redis-backed Sliding-Window Rate Limiter (Phase 6).

Implements RateLimitChecker protocol from Phase 5.
Uses Redis Sorted Sets (ZSET) for mathematically exact sliding-window rate limiting
for both REQUESTS_PER_MINUTE and TOKENS_PER_MINUTE.

Security policy: Fail-closed. If Redis is unreachable, requests are denied by default.
"""
import logging
import time
import uuid
from typing import Optional, Tuple
import redis
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.budget import Budget
from app.models.tool import Tool
from app.schemas.policy import DecisionInput

log = logging.getLogger(__name__)

DEFAULT_REQUESTS_PER_MINUTE = 60
DEFAULT_TOKENS_PER_MINUTE = 100000
WINDOW_SECONDS = 60.0


class RedisRateLimitChecker:
    """Sliding-window rate limiter backed by Redis sorted sets (ZSET).

    Conforms to RateLimitChecker protocol:
        (db: Session, input_data: DecisionInput, agent: Agent, tool: Tool) -> (bool, Optional[str])
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        default_requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        default_tokens_per_minute: int = DEFAULT_TOKENS_PER_MINUTE,
        window_seconds: float = WINDOW_SECONDS,
    ):
        self.redis = redis_client
        self.default_requests_per_minute = default_requests_per_minute
        self.default_tokens_per_minute = default_tokens_per_minute
        self.window_seconds = window_seconds

    def _get_request_key(self, agent_id: uuid.UUID) -> str:
        return f"ratelimit:requests:{agent_id}"

    def _get_token_key(self, agent_id: uuid.UUID) -> str:
        return f"ratelimit:tokens:{agent_id}"

    def reset(self, agent_id: uuid.UUID) -> None:
        """Utility for test suites to clear rate limit windows for an agent."""
        try:
            self.redis.delete(self._get_request_key(agent_id), self._get_token_key(agent_id))
        except Exception:
            pass

    def __call__(
        self,
        db: Session,
        input_data: DecisionInput,
        agent: Agent,
        tool: Tool,
    ) -> Tuple[bool, Optional[str]]:
        """Evaluate sliding-window rate limits for the requesting agent.

        Returns (allowed: bool, reason: Optional[str]).
        """
        # Determine configured limits from Budget table or fallbacks
        budget_row = (
            db.query(Budget)
            .filter(Budget.agent_id == agent.id)
            .first()
        )
        max_requests = (
            budget_row.max_requests_per_minute
            if budget_row and budget_row.max_requests_per_minute is not None
            else self.default_requests_per_minute
        )
        max_tokens = self.default_tokens_per_minute

        req_key = self._get_request_key(agent.id)
        token_key = self._get_token_key(agent.id)

        now = time.time()
        clear_before = now - self.window_seconds

        try:
            # ---------------------------------------------------------------
            # 1. Evaluate Request Rate Limit (Sliding Window via ZSET)
            # ---------------------------------------------------------------
            pipe = self.redis.pipeline()
            # Remove entries older than window
            pipe.zremrangebyscore(req_key, "-inf", clear_before)
            # Count remaining requests in current window
            pipe.zcard(req_key)
            results = pipe.execute()
            current_requests = results[1]

            if current_requests >= max_requests:
                return (
                    False,
                    f"Rate limit exceeded for agent '{agent.name}': "
                    f"{current_requests} requests in last {int(self.window_seconds)}s "
                    f"exceeds limit of {max_requests} req/min.",
                )

            # ---------------------------------------------------------------
            # 2. Evaluate Token Rate Limit (Sliding Window via ZSET)
            # ---------------------------------------------------------------
            tokens_in_request = input_data.estimated_tokens or 0
            if tokens_in_request > 0:
                pipe = self.redis.pipeline()
                pipe.zremrangebyscore(token_key, "-inf", clear_before)
                pipe.zrangebyscore(token_key, "-inf", "+inf")
                token_results = pipe.execute()
                raw_entries = token_results[1]

                current_tokens = 0
                for entry in raw_entries:
                    if isinstance(entry, bytes):
                        entry_str = entry.decode("utf-8")
                    else:
                        entry_str = str(entry)
                    try:
                        current_tokens += int(entry_str.split(":")[0])
                    except (ValueError, IndexError):
                        pass

                if current_tokens + tokens_in_request > max_tokens:
                    return (
                        False,
                        f"Token rate limit exceeded for agent '{agent.name}': "
                        f"{current_tokens + tokens_in_request} tokens in last {int(self.window_seconds)}s "
                        f"exceeds limit of {max_tokens} tokens/min.",
                    )

            # ---------------------------------------------------------------
            # 3. Record This Request in Redis Sliding Window
            # ---------------------------------------------------------------
            request_member = f"{uuid.uuid4().hex}:{now}"
            pipe = self.redis.pipeline()
            pipe.zadd(req_key, {request_member: now})
            pipe.expire(req_key, int(self.window_seconds * 2))

            if tokens_in_request > 0:
                token_member = f"{tokens_in_request}:{uuid.uuid4().hex}:{now}"
                pipe.zadd(token_key, {token_member: now})
                pipe.expire(token_key, int(self.window_seconds * 2))

            pipe.execute()
            return True, None

        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            # FAIL-CLOSED SECURITY POLICY:
            # In a governance and security proxy, if telemetry/rate-limiting
            # infrastructure fails, the proxy must deny by default rather than
            # allowing unmonitored execution.
            log.error(f"Redis rate limiter connection error: {e}")
            return False, "Rate limit check failed: Redis connection unavailable (fail-closed policy)."
