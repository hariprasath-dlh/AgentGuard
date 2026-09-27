"""Google OAuth 2.0 Service for AgentGuard.

Provides state creation & validation (CSRF protection), authorization URL generation,
token exchange, and cryptographically verified ID token decoding via google-auth.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings

log = logging.getLogger(__name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def generate_oauth_state(redirect_target: Optional[str] = None) -> str:
    """Generate a signed, timestamped, tamper-proof state token for CSRF defense."""
    payload = {
        "nonce": uuid.uuid4().hex,
        "redirect_target": redirect_target or settings.FRONTEND_URL,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def validate_oauth_state(state: str) -> Optional[Dict[str, Any]]:
    """Validate the cryptographic signature and expiration of an OAuth state parameter.

    Returns the decoded payload if valid, or None if tampered/expired.
    """
    if not state:
        return None
    try:
        payload = jwt.decode(state, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except (jwt.PyJWTError, Exception) as exc:
        log.warning(f"OAuth state validation failed: {exc}")
        return None


def get_google_auth_url(state: str) -> str:
    """Construct the Google OAuth 2.0 Authorization URL."""
    from urllib.parse import urlencode

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_google_code(code: str) -> Dict[str, Any]:
    """Exchange authorization code for tokens via Google OAuth token endpoint."""
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    response = httpx.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=10.0)
    if response.status_code != 200:
        log.error(f"Google token exchange failed ({response.status_code}): {response.text}")
        raise ValueError(f"Failed to exchange code with Google: {response.text}")
    return response.json()


def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """Cryptographically verify Google ID token signature and audience.

    Never trust unverified claims from the client.
    """
    request = google_requests.Request()
    try:
        id_info = google_id_token.verify_oauth2_token(
            id_token_str, request, settings.GOOGLE_CLIENT_ID
        )
    except Exception as exc:
        log.error(f"Google ID token signature verification failed: {exc}")
        raise ValueError(f"Invalid Google ID token: {exc}") from exc

    if not id_info.get("email"):
        raise ValueError("Google ID token missing email claim")

    if not id_info.get("email_verified", False):
        raise ValueError("Google email address is not verified by Google")

    return id_info


# In-memory fallback dictionary: {code: (access_token, expiration_timestamp)}
_memory_exchange_cache: Dict[str, tuple[str, float]] = {}


def store_oauth_exchange_code(access_token: str, ttl_seconds: int = 60) -> str:
    """Store JWT access_token against a one-time high-entropy opaque exchange code.

    Prevents JWT token exposure in browser URLs, history, server logs, and Referer headers.
    """
    import secrets
    import time

    code = secrets.token_urlsafe(32)

    # 1. Attempt Redis storage if available
    try:
        from app.core.redis import get_redis_client

        r = get_redis_client()
        r.set(f"oauth_exchange:{code}", access_token, ex=ttl_seconds)
        return code
    except Exception as exc:
        log.debug(f"Redis unavailable for OAuth exchange code, using in-memory store: {exc}")

    # 2. In-memory fallback
    now = time.time()
    # Prune expired keys
    expired = [k for k, (_, exp) in _memory_exchange_cache.items() if exp < now]
    for k in expired:
        _memory_exchange_cache.pop(k, None)

    _memory_exchange_cache[code] = (access_token, now + ttl_seconds)
    return code


def consume_oauth_exchange_code(code: str) -> Optional[str]:
    """Retrieve and immediately invalidate a one-time OAuth exchange code (single-use guarantee).

    Returns access_token if code was valid and unconsumed, or None otherwise.
    """
    import time

    if not code:
        return None

    # 1. Try Redis first
    try:
        from app.core.redis import get_redis_client

        r = get_redis_client()
        key = f"oauth_exchange:{code}"
        pipe = r.pipeline()
        pipe.get(key)
        pipe.delete(key)
        results = pipe.execute()
        val = results[0]
        if val:
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)
    except Exception as exc:
        log.debug(f"Redis unavailable for OAuth exchange retrieval, falling back: {exc}")

    # 2. In-memory fallback (single use: pop removes it immediately)
    item = _memory_exchange_cache.pop(code, None)
    if item:
        access_token, exp = item
        if time.time() <= exp:
            return access_token

    return None

