"""Human-in-the-Loop (HITL) API endpoints (Phase 9).

RBAC Matrix:
  - GET /hitl:              MANAGER, ADMIN
  - GET /hitl/{id}:         MANAGER, ADMIN
  - POST /hitl/{id}/approve: MANAGER, ADMIN
  - POST /hitl/{id}/deny:    MANAGER, ADMIN

Invariants:
1. Commit-before-execute on approve: Approval decision and HITL_APPROVED audit entry
   are durably committed to the database before the mock tool handler runs.
2. Safe execution: Mock handler errors do not crash the endpoint or revoke approval;
   the error is recorded in output_payload and stamped as TOOL_EXECUTION_FAILED in the audit log.
3. Expiration: Requests past their expires_at are marked EXPIRED and reject decisions.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.hitl_request import HITLRequest
from app.models.tool_request import ToolRequest
from app.schemas.auth import RoleEnum
from app.schemas.hitl import (
    HITLRequestListResponse,
    HITLRequestResponse,
    HITLReviewRequest,
)
from app.security.deps import AuthenticatedUser, require_role
from app.services.audit_vault import record_audit_log
from app.services.mock_tools import get_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hitl", tags=["hitl"])

_HITL_ROLES = (RoleEnum.ADMIN, RoleEnum.MANAGER)


def _enrich_hitl_response(hitl: HITLRequest) -> HITLRequestResponse:
    """Build response model from HITLRequest with linked ToolRequest details."""
    tool_name = None
    agent_id = None
    input_payload = None
    output_payload = None

    if hitl.tool_request is not None:
        agent_id = hitl.tool_request.agent_id
        input_payload = hitl.tool_request.input_payload
        output_payload = hitl.tool_request.output_payload
        if hitl.tool_request.tool is not None:
            tool_name = hitl.tool_request.tool.name

    return HITLRequestResponse(
        id=hitl.id,
        organization_id=hitl.organization_id,
        tool_request_id=hitl.tool_request_id,
        status=hitl.status,
        reviewer_id=hitl.reviewer_id,
        review_notes=hitl.review_notes,
        expires_at=hitl.expires_at,
        reviewed_at=hitl.reviewed_at,
        created_at=hitl.created_at,
        updated_at=hitl.updated_at,
        tool_name=tool_name,
        agent_id=agent_id,
        input_payload=input_payload,
        output_payload=output_payload,
    )


def sweep_expired_hitl_requests(
    db: Session, organization_id: Optional[uuid.UUID] = None
) -> int:
    """Sweep and transition all expired PENDING requests to EXPIRED.

    Callable as a periodic job or directly by tests.
    """
    now = datetime.now(timezone.utc)
    query = db.query(HITLRequest).filter(
        HITLRequest.status == "PENDING",
        HITLRequest.expires_at.isnot(None),
        HITLRequest.expires_at <= now,
    )
    if organization_id is not None:
        query = query.filter(HITLRequest.organization_id == organization_id)

    expired_items = query.all()
    if not expired_items:
        return 0

    for item in expired_items:
        item.status = "EXPIRED"

    db.commit()
    return len(expired_items)


def _check_lazy_expiration(db: Session, hitl: HITLRequest) -> bool:
    """Check if a pending request is past its expiration.

    Transitions status to EXPIRED and commits if expired.
    Returns True if the request is or became EXPIRED.
    """
    if hitl.status == "PENDING" and hitl.expires_at is not None:
        now = datetime.now(timezone.utc)
        if now >= hitl.expires_at:
            hitl.status = "EXPIRED"
            db.commit()
            return True
    return hitl.status == "EXPIRED"


@router.get("", response_model=HITLRequestListResponse)
def list_hitl_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. PENDING, APPROVED, DENIED, EXPIRED)"),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_HITL_ROLES)),
) -> HITLRequestListResponse:
    """List HITL requests for the caller's organization with lazy expiration."""
    # Run lazy expiration sweep for caller's organization
    sweep_expired_hitl_requests(db, organization_id=current_user.organization_id)

    query = (
        db.query(HITLRequest)
        .options(joinedload(HITLRequest.tool_request).joinedload(ToolRequest.tool))
        .filter(HITLRequest.organization_id == current_user.organization_id)
    )
    if status_filter:
        query = query.filter(HITLRequest.status == status_filter.upper())

    total = query.count()
    records = (
        query.order_by(HITLRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_enrich_hitl_response(r) for r in records]
    return HITLRequestListResponse(total=total, items=items)


@router.get("/{hitl_id}", response_model=HITLRequestResponse)
def get_hitl_request(
    hitl_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_HITL_ROLES)),
) -> HITLRequestResponse:
    """Retrieve a single HITL request by ID within the caller's organization."""
    hitl = (
        db.query(HITLRequest)
        .options(joinedload(HITLRequest.tool_request).joinedload(ToolRequest.tool))
        .filter(
            HITLRequest.id == hitl_id,
            HITLRequest.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not hitl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HITL request '{hitl_id}' not found",
        )

    _check_lazy_expiration(db, hitl)
    return _enrich_hitl_response(hitl)


@router.post("/{hitl_id}/approve", response_model=HITLRequestResponse)
def approve_hitl_request(
    hitl_id: uuid.UUID,
    review_data: Optional[HITLReviewRequest] = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_HITL_ROLES)),
) -> HITLRequestResponse:
    """Approve a pending HITL request and resume tool execution.

    Commit-Before-Execute Ordering:
      1. Verify PENDING status and non-expired.
      2. Update hitl_request to APPROVED and tool_request to APPROVED.
      3. Write and commit the HITL_APPROVED audit log entry.
      4. Execute mock tool handler (if registered).
      5. Write and commit the TOOL_EXECUTED / TOOL_EXECUTION_FAILED audit log entry.
    """
    hitl = (
        db.query(HITLRequest)
        .options(joinedload(HITLRequest.tool_request).joinedload(ToolRequest.tool))
        .filter(
            HITLRequest.id == hitl_id,
            HITLRequest.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not hitl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HITL request '{hitl_id}' not found",
        )

    # Check lazy expiration
    if _check_lazy_expiration(db, hitl) or hitl.status == "EXPIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HITL request has expired and cannot be approved",
        )

    if hitl.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HITL request is already resolved with status '{hitl.status}'",
        )

    tool_request = hitl.tool_request
    tool_name = (
        tool_request.tool.name if (tool_request and tool_request.tool) else None
    )
    review_notes = review_data.review_notes if review_data else None
    now = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # STEP 1: Update status and write HITL_APPROVED audit entry
    # -----------------------------------------------------------------------
    hitl.status = "APPROVED"
    hitl.reviewer_id = current_user.id
    hitl.reviewed_at = now
    hitl.review_notes = review_notes

    if tool_request is not None:
        tool_request.decision = "APPROVED"

    approve_payload = {
        "action": "approve",
        "reviewer_id": str(current_user.id),
        "reviewer_email": current_user.email,
        "review_notes": review_notes,
        "hitl_id": str(hitl.id),
        "tool_request_id": str(hitl.tool_request_id),
        "tool_name": tool_name,
    }
    record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        agent_id=tool_request.agent_id if tool_request else None,
        tool_id=tool_request.tool_id if tool_request else None,
        event_type="HITL_APPROVED",
        decision="APPROVED",
        payload=approve_payload,
        request_id=tool_request.id if tool_request else hitl.id,
        tool_name=tool_name,
    )

    # -----------------------------------------------------------------------
    # STEP 2: COMMIT-BEFORE-EXECUTE HARD GATE
    # Approval must be durably stored in PostgreSQL before handler runs.
    # -----------------------------------------------------------------------
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to commit approval decision for HITL {hitl_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record approval decision in audit log.",
        )

    # -----------------------------------------------------------------------
    # STEP 3: Execute mock tool handler (Safe resume execution)
    # -----------------------------------------------------------------------
    mock_handler = get_handler(tool_name) if tool_name else None
    execution_status = "skipped_no_handler"
    execution_output = None
    handler_error = None

    if mock_handler is not None and tool_request is not None:
        params = (
            tool_request.input_payload.get("parameters", {})
            if tool_request.input_payload
            else {}
        )
        try:
            execution_output = mock_handler(params)
            execution_status = "executed"
        except Exception as exc:
            logger.error(f"Mock handler '{tool_name}' raised during resume: {exc}")
            execution_status = "error"
            handler_error = str(exc)
            execution_output = {"execution_status": "error", "error": handler_error}
    elif mock_handler is None and tool_request is not None:
        execution_output = {
            "execution_status": "skipped_no_handler",
            "reason": f"No mock handler registered for tool '{tool_name}'",
        }

    # -----------------------------------------------------------------------
    # STEP 4: Record execution outcome and write second audit entry
    # -----------------------------------------------------------------------
    if tool_request is not None:
        tool_request.output_payload = execution_output

    if execution_status == "executed":
        exec_payload = {
            "action": "execute",
            "tool_name": tool_name,
            "tool_request_id": str(hitl.tool_request_id),
            "output": execution_output,
            "execution_status": "executed",
        }
        record_audit_log(
            db=db,
            organization_id=current_user.organization_id,
            agent_id=tool_request.agent_id,
            tool_id=tool_request.tool_id,
            event_type="TOOL_EXECUTED",
            decision="EXECUTED",
            payload=exec_payload,
            request_id=tool_request.id,
            tool_name=tool_name,
        )
    elif execution_status == "error":
        exec_payload = {
            "action": "execute",
            "tool_name": tool_name,
            "tool_request_id": str(hitl.tool_request_id),
            "error": handler_error,
            "execution_status": "error",
        }
        record_audit_log(
            db=db,
            organization_id=current_user.organization_id,
            agent_id=tool_request.agent_id,
            tool_id=tool_request.tool_id,
            event_type="TOOL_EXECUTION_FAILED",
            decision="ERROR",
            payload=exec_payload,
            request_id=tool_request.id,
            tool_name=tool_name,
        )
    else:
        exec_payload = {
            "action": "execute",
            "tool_name": tool_name,
            "tool_request_id": str(hitl.tool_request_id),
            "execution_status": "skipped_no_handler",
        }
        record_audit_log(
            db=db,
            organization_id=current_user.organization_id,
            agent_id=tool_request.agent_id,
            tool_id=tool_request.tool_id,
            event_type="TOOL_EXECUTION_SKIPPED",
            decision="SKIPPED",
            payload=exec_payload,
            request_id=tool_request.id,
            tool_name=tool_name,
        )

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to commit execution audit log for HITL {hitl_id}: {exc}")

    return _enrich_hitl_response(hitl)


@router.post("/{hitl_id}/deny", response_model=HITLRequestResponse)
def deny_hitl_request(
    hitl_id: uuid.UUID,
    review_data: Optional[HITLReviewRequest] = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_HITL_ROLES)),
) -> HITLRequestResponse:
    """Deny a pending HITL request. No mock tool handler is executed."""
    hitl = (
        db.query(HITLRequest)
        .options(joinedload(HITLRequest.tool_request).joinedload(ToolRequest.tool))
        .filter(
            HITLRequest.id == hitl_id,
            HITLRequest.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not hitl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HITL request '{hitl_id}' not found",
        )

    # Check lazy expiration
    if _check_lazy_expiration(db, hitl) or hitl.status == "EXPIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HITL request has expired and cannot be denied",
        )

    if hitl.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HITL request is already resolved with status '{hitl.status}'",
        )

    tool_request = hitl.tool_request
    tool_name = (
        tool_request.tool.name if (tool_request and tool_request.tool) else None
    )
    review_notes = review_data.review_notes if review_data else None
    now = datetime.now(timezone.utc)

    # Update status to DENIED
    hitl.status = "DENIED"
    hitl.reviewer_id = current_user.id
    hitl.reviewed_at = now
    hitl.review_notes = review_notes

    if tool_request is not None:
        tool_request.decision = "DENIED"

    deny_payload = {
        "action": "deny",
        "reviewer_id": str(current_user.id),
        "reviewer_email": current_user.email,
        "review_notes": review_notes,
        "hitl_id": str(hitl.id),
        "tool_request_id": str(hitl.tool_request_id),
        "tool_name": tool_name,
    }
    record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        agent_id=tool_request.agent_id if tool_request else None,
        tool_id=tool_request.tool_id if tool_request else None,
        event_type="HITL_DENIED",
        decision="DENIED",
        payload=deny_payload,
        request_id=tool_request.id if tool_request else hitl.id,
        tool_name=tool_name,
    )

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to commit denial decision for HITL {hitl_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record denial decision in audit log.",
        )

    return _enrich_hitl_response(hitl)
