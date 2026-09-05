"""Pre-dispatch Guard Gateway (Phase 7).

Exposes the PolicyEngine as an HTTP endpoint: POST /api/v1/guard/check.
This is the single, unavoidable chokepoint between an AI agent and the tools it calls.

CRITICAL INVARIANTS:
1. Pure translation/orchestration: No decision logic in this router.
2. Commit-before-execute: AuditLog (and ToolRequest/HITLRequest) must be committed
   to the database BEFORE any mock tool handler is invoked. If the commit fails,
   the request terminates with HTTP 500 and the mock handler is never reached.
3. Server-generated request_id (UUID): Client-supplied IDs are never trusted.
4. Mock handler errors do not hide ALLOW: If a mock handler raises, the error is
   recorded in output_payload, but the ALLOW decision is still returned.
5. Missing handlers are recorded explicitly: An ALLOW on an unhandled tool logs
   'skipped_no_handler' so audit trails never overstate execution.
"""
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hitl_request import HITLRequest
from app.models.tool import Tool
from app.models.tool_request import ToolRequest
from app.repositories.registry import ToolRepository
from app.schemas.policy import (
    CallerIdentity,
    DecisionEnum,
    DecisionInput,
    GuardResponse,
)
from app.security.deps import AuthenticatedAgent, get_current_agent
from app.services.audit_vault import record_audit_log
from app.services.factory import create_policy_engine
from app.services.mock_tools import get_handler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["guard"])


@router.post("/guard/check", response_model=GuardResponse)
def guard_check(
    request_data: DecisionInput,
    agent: AuthenticatedAgent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> GuardResponse:
    """Evaluate a proposed tool call through the PolicyEngine chokepoint.

    Strict execution flow:
      1. Authenticate agent & construct CallerIdentity
      2. Call deterministic PolicyEngine (via Phase 6 Redis-wired factory)
      3. Create ToolRequest, AuditLog (with monotonic sequence_number), and HITLRequest if PENDING
      4. db.commit() -- HARD GATE: if commit fails, abort with 500 (mock tool never called)
      5. If ALLOW and mock handler exists, execute safe mock tool
      6. Return decision response to agent
    """
    start_time = time.time()
    server_request_id = uuid.uuid4()

    # 1. Resolve caller identity
    caller_id = agent.agent_id if agent.agent_id is not None else request_data.agent_id
    caller = CallerIdentity(
        caller_type="AGENT",
        caller_id=caller_id,
        organization_id=agent.organization_id,
        is_authenticated=True,
    )

    # 2. Evaluate policy via deterministic PolicyEngine
    engine = create_policy_engine(db=db)
    decision_output = engine.evaluate(input_data=request_data, caller=caller)

    # Resolve tool if present in org
    tool_repo = ToolRepository(db=db, organization_id=agent.organization_id)
    tool: Optional[Tool] = tool_repo.get_by_name(request_data.tool_name)
    tool_id = tool.id if tool else None

    # Determine mock handler availability for ALLOW
    mock_handler = get_handler(request_data.tool_name)
    execution_skipped = (
        decision_output.decision == DecisionEnum.ALLOW and mock_handler is None
    )

    # Prepare audit payload (record_audit_log will stamp "timestamp" as the canonical value)
    audit_payload = {
        "request_id": str(server_request_id),
        "tool_name": request_data.tool_name,
        "action": request_data.action,
        "parameters": request_data.parameters,
        "estimated_tokens": request_data.estimated_tokens,
        "estimated_cost": request_data.estimated_cost,
        "metadata": request_data.metadata,
        "checks": {k: v.model_dump() for k, v in decision_output.checks.items()},
    }
    if execution_skipped:
        audit_payload["execution_status"] = "skipped_no_handler"
        audit_payload["execution_note"] = f"No mock handler registered for tool '{request_data.tool_name}'"

    # 3. Create AuditLog row via audit_vault (real SHA-256 hash chain, row-level org lock)
    audit_log_id = uuid.uuid4()
    audit_log = record_audit_log(
        db=db,
        organization_id=agent.organization_id,
        agent_id=request_data.agent_id,
        tool_id=tool_id,
        event_type="TOOL_REQUEST_EVALUATED",
        decision=decision_output.decision.value,
        payload=audit_payload,
        request_id=server_request_id,
        tool_name=request_data.tool_name,
        audit_log_id=audit_log_id,
    )

    # Create ToolRequest row if tool is valid (FK constraint on tool_id)
    tool_request = None
    if tool_id is not None:
        initial_output_payload = None
        if execution_skipped:
            initial_output_payload = {
                "execution_status": "skipped_no_handler",
                "reason": f"No mock handler registered for tool '{request_data.tool_name}'",
            }

        tool_request = ToolRequest(
            id=server_request_id,
            organization_id=agent.organization_id,
            agent_id=request_data.agent_id,
            tool_id=tool_id,
            audit_log_id=audit_log_id,
            decision=decision_output.decision.value,
            reason=decision_output.reason,
            input_payload={
                "action": request_data.action,
                "parameters": request_data.parameters,
                "metadata": request_data.metadata,
            },
            output_payload=initial_output_payload,
            latency_ms=(time.time() - start_time) * 1000.0,
        )
        db.add(tool_request)

        # If decision is PENDING, create HITLRequest row with 24-hour expiration
        if decision_output.decision == DecisionEnum.PENDING:
            hitl_req = HITLRequest(
                organization_id=agent.organization_id,
                tool_request_id=tool_request.id,
                status="PENDING",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add(hitl_req)

    # 4. HARD GATE: Commit audit and decision to DB before any execution
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to commit audit record for request {server_request_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record audit trail. Action was blocked.",
        )

    # 5. Safe Mock Execution (ONLY after commit succeeded, and ONLY for ALLOW)
    if decision_output.decision == DecisionEnum.ALLOW and mock_handler is not None:
        try:
            handler_result = mock_handler(request_data.parameters)
            if tool_request is not None:
                tool_request.output_payload = handler_result
                tool_request.latency_ms = (time.time() - start_time) * 1000.0
                db.commit()
        except Exception as handler_exc:
            logger.error(
                f"Mock handler '{request_data.tool_name}' failed for request {server_request_id}: {handler_exc}"
            )
            if tool_request is not None:
                tool_request.output_payload = {
                    "execution_status": "error",
                    "error": str(handler_exc),
                }
                tool_request.latency_ms = (time.time() - start_time) * 1000.0
                try:
                    db.commit()
                except Exception:
                    db.rollback()

    # 6. Return standard response contract
    return GuardResponse(
        decision=decision_output.decision,
        request_id=server_request_id,
        reason=decision_output.reason,
    )
