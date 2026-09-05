"""Pydantic schemas for the Cryptographic Audit Vault (Phase 8).

Defines response models for audit log retrieval and hash chain verification.
"""
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Single audit log entry reflecting cryptographic hash chain metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: Optional[uuid.UUID] = None
    tool_id: Optional[uuid.UUID] = None
    event_type: str
    decision: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    previous_hash: Optional[str] = None
    current_hash: str
    sequence_number: Optional[int] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated response containing a list of audit logs."""
    total: int
    items: list[AuditLogResponse]


class AuditVerificationResponse(BaseModel):
    """Result of cryptographic hash chain verification.

    Notice: This describes a tamper-evident cryptographic hash chain. It detects
    tampering after the fact by verifying cryptographic continuity.
    """
    status: str  # "VALID" or "INVALID"
    total_records: int
    message: str
    broken_record_id: Optional[uuid.UUID] = None
    broken_sequence_number: Optional[int] = None
    error_type: Optional[str] = None
    details: Optional[str] = None
    early_exit_note: Optional[str] = None
    duration_ms: Optional[float] = None
