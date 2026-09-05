"""Audit Vault API endpoints (Phase 8).

RBAC Matrix:
  - GET /audit:         ADMIN, AUDITOR
  - GET /audit/{id}:    ADMIN, AUDITOR
  - POST /audit/verify: ADMIN, AUDITOR

All endpoints enforce strict organization isolation.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditVerificationResponse,
)
from app.schemas.auth import RoleEnum
from app.security.deps import AuthenticatedUser, require_role
from app.services.audit_vault import verify_organization_chain

router = APIRouter(prefix="/audit", tags=["audit"])

_AUDIT_ROLES = (RoleEnum.ADMIN, RoleEnum.AUDITOR)


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_AUDIT_ROLES)),
) -> AuditLogListResponse:
    """List audit log records for the caller's organization in reverse chronological sequence."""
    query = db.query(AuditLog).filter(AuditLog.organization_id == current_user.organization_id)
    total = query.count()
    items = (
        query.order_by(AuditLog.sequence_number.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return AuditLogListResponse(total=total, items=items)


@router.get("/{audit_id}", response_model=AuditLogResponse)
def get_audit_log(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_AUDIT_ROLES)),
) -> AuditLogResponse:
    """Retrieve a single audit log record by ID within the caller's organization."""
    log = (
        db.query(AuditLog)
        .filter(
            AuditLog.id == audit_id,
            AuditLog.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log record '{audit_id}' not found in organization",
        )
    return log


@router.post("/verify", response_model=AuditVerificationResponse)
def verify_audit_vault(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_role(*_AUDIT_ROLES)),
) -> AuditVerificationResponse:
    """Trigger cryptographic verification of the organization's tamper-evident hash chain.

    Scans records sequentially from sequence 1 onwards. Early-exits on the first
    detected discontinuity, sequence gap, or hash mismatch, identifying the exact
    compromised record.
    """
    result = verify_organization_chain(db=db, organization_id=current_user.organization_id)
    return AuditVerificationResponse(**result)
