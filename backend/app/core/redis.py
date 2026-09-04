"""Redis connection management for AgentGuard.

Provides thread-safe connection pooling, client instantiation, and FastAPI dependency.
Reads REDIS_URL from application settings / environment.
"""
from typing import Generator, Optional
import redis

from app.core.config import settings

# Global connection pool
_pool: Optional[redis.ConnectionPool] = None


def get_redis_pool() -> redis.ConnectionPool:
    """Get or create the singleton Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            max_connections=50,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    return _pool


def get_redis_client() -> redis.Redis:
    """Instantiate a Redis client using the shared connection pool."""
    return redis.Redis(connection_pool=get_redis_pool())


def get_redis() -> Generator[redis.Redis, None, None]:
    """FastAPI dependency for obtaining a Redis client.

    Usage:
        @router.get("/example")
        def route(r: redis.Redis = Depends(get_redis)):
            ...
    """
    client = get_redis_client()
    try:
        yield client
    finally:
        pass
