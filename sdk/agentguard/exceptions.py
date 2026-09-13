"""Structured exceptions for the AgentGuard SDK.

All SDK exceptions inherit from AgentGuardError so callers can catch broadly or specifically.
"""
from typing import Optional


class AgentGuardError(Exception):
    """Base exception for all AgentGuard SDK errors."""
    pass


class AgentGuardDenied(AgentGuardError):
    """Raised when a proposed tool call is blocked (DENIED) by AgentGuard governance.

    Attributes:
        reason: Human-readable explanation of why the action was denied.
        request_id: Server-assigned UUID tracking the decision in the audit vault.
    """
    def __init__(self, reason: str, request_id: Optional[str] = None) -> None:
        self.reason = reason
        self.request_id = request_id
        msg = f"AgentGuard denied tool call: {reason}"
        if request_id:
            msg += f" (request_id={request_id})"
        super().__init__(msg)


class AgentGuardPending(AgentGuardError):
    """Raised when a proposed tool call requires Human-in-the-Loop (HITL) approval (PENDING).

    This is not an unexpected failure; it indicates the agent must pause until a human
    reviews the request. The request_id can be used to track or poll approval status.

    Attributes:
        reason: Policy explanation detailing why human review was flagged.
        request_id: Server-assigned UUID representing the pending HITL request.
    """
    def __init__(self, reason: str, request_id: Optional[str] = None) -> None:
        self.reason = reason
        self.request_id = request_id
        msg = f"AgentGuard queued action for human approval: {reason}"
        if request_id:
            msg += f" (request_id={request_id})"
        super().__init__(msg)


class AgentGuardAuthenticationError(AgentGuardError):
    """Raised when the backend rejects client credentials (HTTP 401 Unauthorized or 403 Forbidden).

    Attributes:
        status_code: HTTP status code received (typically 401 or 403).
        detail: Error details returned by the backend.
    """
    def __init__(self, status_code: int = 401, detail: Optional[str] = None) -> None:
        self.status_code = status_code
        self.detail = detail
        msg = f"AgentGuard authentication failed (HTTP {status_code})"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class AgentGuardTimeout(AgentGuardError):
    """Raised when AgentGuard cannot be reached within the configured timeout.

    NOTE: Raised for both connection timeouts and connection refusals — treat as
    'could not reach the backend', not literally 'timed out'.
    """
    def __init__(self, message: str = "Request to AgentGuard timed out or connection refused") -> None:
        self.message = message
        super().__init__(message)


class AgentGuardServerError(AgentGuardError):
    """Raised when the AgentGuard backend returns an unexpected 5xx response or unparseable payload.

    Attributes:
        status_code: HTTP response status code.
        detail: Backend error detail message if available.
        raw_response: Raw response body string for debugging.
    """
    def __init__(
        self,
        status_code: int,
        detail: Optional[str] = None,
        raw_response: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.raw_response = raw_response
        msg = f"AgentGuard backend error (HTTP {status_code})"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)
