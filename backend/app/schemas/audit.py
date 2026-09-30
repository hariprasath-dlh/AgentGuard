"""Pydantic schemas for the Cryptographic Audit Vault (Phase 8).

Defines response models for audit log retrieval and hash chain verification.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Single audit log entry reflecting cryptographic hash chain metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    tool_id: uuid.UUID | None = None
    event_type: str
    decision: str | None = None
    payload: dict[str, Any] | None = None
    previous_hash: str | None = None
    current_hash: str
    sequence_number: int | None = None
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
    broken_record_id: uuid.UUID | None = None
    broken_sequence_number: int | None = None
    error_type: str | None = None
    details: str | None = None
    early_exit_note: str | None = None
    duration_ms: float | None = None
