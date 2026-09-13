"""Core guard evaluation logic for translating HTTP responses into decisions and exceptions.

CRITICAL INVARIANTS:
1. Safe Retry: Retries ONLY on network-level connection failures and connect timeouts
   where no response was received. Never retries once the backend has received the request
   and generated an HTTP response (ALLOW, DENY, PENDING, or error), preventing double
   execution or duplicate budget/rate-limit deduction.
2. Translation: ALLOW returns GuardResult; DENY raises AgentGuardDenied; PENDING raises
   AgentGuardPending (unless raise_for_status=False is specified).
"""
import time
import uuid
from typing import Any, Optional, Union
import httpx

from agentguard.exceptions import (
    AgentGuardAuthenticationError,
    AgentGuardDenied,
    AgentGuardPending,
    AgentGuardServerError,
    AgentGuardTimeout,
)
from agentguard.models import GuardRequest, GuardResult


def evaluate_guard(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    tool: str,
    parameters: Optional[dict[str, Any]] = None,
    action: str = "execute",
    agent_id: Optional[Union[uuid.UUID, str]] = None,
    estimated_tokens: int = 0,
    estimated_cost: float = 0.0,
    metadata: Optional[dict[str, Any]] = None,
    timeout: float = 5.0,
    max_retries: int = 1,
    retry_backoff: float = 0.2,
    raise_for_status: bool = True,
) -> GuardResult:
    """Send a proposed tool call to AgentGuard /guard/check and evaluate the response."""
    # Ensure agent_id is provided as a UUID string (or zero-UUID if backend extracts from API key)
    resolved_agent_id = str(agent_id) if agent_id else "00000000-0000-0000-0000-000000000000"

    request_payload = GuardRequest(
        agent_id=resolved_agent_id,
        tool_name=tool,
        action=action,
        parameters=parameters or {},
        estimated_tokens=estimated_tokens,
        estimated_cost=estimated_cost,
        metadata=metadata,
    ).model_dump(mode="json")

    endpoint = f"{base_url.rstrip('/')}/guard/check"

    response = None
    last_network_exc = None

    # Safe Retry Loop: Retries ONLY when no HTTP response was received.
    for attempt in range(max_retries + 1):
        try:
            response = client.post(
                endpoint,
                json=request_payload,
                headers=headers,
                timeout=timeout,
            )
            # Response was received: DO NOT RETRY further under any circumstances.
            break
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last_network_exc = exc
            if attempt < max_retries:
                time.sleep(retry_backoff * (2 ** attempt))
                continue
            raise AgentGuardTimeout(
                f"Could not connect to AgentGuard at {endpoint}: {exc}"
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
            last_network_exc = exc
            if attempt < max_retries:
                time.sleep(retry_backoff * (2 ** attempt))
                continue
            raise AgentGuardTimeout(
                f"Request to AgentGuard timed out: {exc}"
            ) from exc
        except httpx.NetworkError as exc:
            last_network_exc = exc
            if attempt < max_retries:
                time.sleep(retry_backoff * (2 ** attempt))
                continue
            raise AgentGuardTimeout(
                f"Network error communicating with AgentGuard: {exc}"
            ) from exc

    if response is None:
        raise AgentGuardTimeout(
            f"Failed to communicate with AgentGuard: {last_network_exc}"
        )

    # -----------------------------------------------------------------------
    # Process HTTP status codes
    # -----------------------------------------------------------------------
    if response.status_code in (401, 403):
        try:
            err_json = response.json()
            detail = err_json.get("detail", response.text)
        except Exception:
            detail = response.text
        raise AgentGuardAuthenticationError(
            status_code=response.status_code,
            detail=detail,
        )

    if response.status_code >= 500:
        try:
            err_json = response.json()
            detail = err_json.get("detail", response.text)
        except Exception:
            detail = response.text
        raise AgentGuardServerError(
            status_code=response.status_code,
            detail=detail,
            raw_response=response.text,
        )

    if response.status_code != 200:
        raise AgentGuardServerError(
            status_code=response.status_code,
            detail=f"Unexpected status code {response.status_code}: {response.text}",
            raw_response=response.text,
        )

    # -----------------------------------------------------------------------
    # Parse Decision Output
    # -----------------------------------------------------------------------
    try:
        body = response.json()
    except Exception as exc:
        raise AgentGuardServerError(
            status_code=200,
            detail=f"Failed to parse JSON response: {exc}",
            raw_response=response.text,
        ) from exc

    decision = str(body.get("decision", "")).upper()
    reason = str(body.get("reason", ""))
    request_id = str(body.get("request_id")) if body.get("request_id") else None

    if decision == "ALLOW":
        return GuardResult(
            allowed=True,
            decision="ALLOW",
            request_id=request_id,
            reason=reason,
            raw_response=body,
        )

    if decision == "DENY":
        if raise_for_status:
            raise AgentGuardDenied(reason=reason, request_id=request_id)
        return GuardResult(
            allowed=False,
            decision="DENY",
            request_id=request_id,
            reason=reason,
            raw_response=body,
        )

    if decision == "PENDING":
        if raise_for_status:
            raise AgentGuardPending(reason=reason, request_id=request_id)
        return GuardResult(
            allowed=False,
            decision="PENDING",
            request_id=request_id,
            reason=reason,
            raw_response=body,
        )

    raise AgentGuardServerError(
        status_code=200,
        detail=f"Unknown governance decision '{decision}'",
        raw_response=response.text,
    )
