"""AgentGuard client for governing autonomous agent tool calls over HTTP."""
import uuid
from typing import Any, Optional, Union
import httpx

from agentguard.guard import evaluate_guard
from agentguard.models import GuardResult


class AgentGuard:
    """Synchronous client for the AgentGuard Core Engine.

    Usage:
        client = AgentGuard(api_key="ag_live_...")
        result = client.guard(tool="read_customer", parameters={"customer_id": "123"})
        if result.allowed:
            # execute tool
            pass

    By default, blocked decisions raise structured exceptions (AgentGuardDenied,
    AgentGuardPending). Pass `raise_for_status=False` to handle decisions via
    the boolean `.allowed` attribute instead.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000/api/v1",
        agent_id: Optional[Union[uuid.UUID, str]] = None,
        timeout: float = 5.0,
        max_retries: int = 1,
        retry_backoff: float = 0.2,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        self._headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "agentguard-python-sdk/0.1.0",
        }

        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    def guard(
        self,
        tool: str,
        parameters: Optional[dict[str, Any]] = None,
        *,
        action: str = "execute",
        agent_id: Optional[Union[uuid.UUID, str]] = None,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        raise_for_status: bool = True,
    ) -> GuardResult:
        """Evaluate a proposed tool call through AgentGuard.

        Args:
            tool: Name of the tool to be executed (e.g. "read_customer").
            parameters: Key-value parameters intended for the tool.
            action: Action verb (default: "execute").
            agent_id: Optional override for the calling agent UUID.
            estimated_tokens: Estimated token usage for cost enforcement.
            estimated_cost: Estimated monetary cost for budget caps.
            metadata: Custom context metadata attached to the request.
            timeout: Per-request timeout in seconds (overrides client default).
            max_retries: Per-request network retry attempts.
            raise_for_status: If True (default), raises AgentGuardDenied or
                AgentGuardPending. If False, returns GuardResult with .allowed=False.

        Returns:
            GuardResult with .allowed=True, .decision, .request_id, and .reason.

        Raises:
            AgentGuardDenied: If policy blocks the action.
            AgentGuardPending: If action requires human review (HITL).
            AgentGuardAuthenticationError: If API key is invalid or revoked.
            AgentGuardTimeout: If the backend is unreachable or times out.
            AgentGuardServerError: If the backend encounters an internal error.
        """
        effective_agent_id = agent_id or self.agent_id
        effective_timeout = timeout if timeout is not None else self.timeout
        effective_retries = max_retries if max_retries is not None else self.max_retries

        return evaluate_guard(
            client=self._client,
            base_url=self.base_url,
            headers=self._headers,
            tool=tool,
            parameters=parameters or {},
            action=action,
            agent_id=effective_agent_id,
            estimated_tokens=estimated_tokens,
            estimated_cost=estimated_cost,
            metadata=metadata,
            timeout=effective_timeout,
            max_retries=effective_retries,
            retry_backoff=self.retry_backoff,
            raise_for_status=raise_for_status,
        )

    def close(self) -> None:
        """Close the underlying HTTP client if owned by this instance."""
        if self._owns_client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> "AgentGuard":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
