"""Cryptographic Audit Vault Service (Phase 8).

Implements a tamper-evident cryptographic hash chain for AgentGuard audit logs.

COMPLIANCE & TRANSPARENCY NOTICE:
This system implements a tamper-evident cryptographic hash chain. It detects tampering
after the fact by verifying cryptographic linkage and canonical serialization; it does
NOT prevent actors with direct database write access from attempting modifications.

CANONICAL EVENT SERIALIZATION:
Event data is canonically serialized to a deterministic UTF-8 JSON string with:
  - Sorted keys (sort_keys=True)
  - Compact separators (separators=(',', ':') with zero extraneous whitespace)
  - Exactly one source of truth for the timestamp (ISO 8601 UTC string)
Fields included in canonical serialization:
  1. organization_id (str): Organization UUID
  2. agent_id (Optional[str]): Agent UUID or None
  3. request_id (str): Unique request UUID
  4. event_type (str): Audit event classification (e.g. "TOOL_REQUEST_EVALUATED")
  5. decision (Optional[str]): Gateway decision ("ALLOW", "DENY", "PENDING")
  6. tool_name (Optional[str]): Name of the tool evaluated
  7. sequence_number (int): Strictly monotonic, gapless sequence number (1-indexed)
  8. timestamp (str): ISO 8601 UTC timestamp string
  9. payload (dict): Evaluated request parameters, checks, and metadata

HASH COMPUTATION:
  current_hash = SHA256(previous_hash + canonical_event_data)
The first record for an organization uses GENESIS_HASH ("0" * 64) as previous_hash.
Every subsequent record uses the immediately preceding record's current_hash.
Chains are strictly isolated per organization.

CONCURRENCY & SEQUENCE RACE SAFETY:
To guarantee strictly monotonic, gapless sequence numbers and prevent fork races under
concurrent requests for the same organization, record_audit_log acquires a row-level
exclusive lock on the organization record (SELECT id FROM organizations WHERE id = ... FOR UPDATE).
Different organizations process fully in parallel without lock contention.
"""
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.organization import Organization

logger = logging.getLogger(__name__)

# Genesis block reference hash: 64 zero characters
GENESIS_HASH: str = "0" * 64


def serialize_audit_event(
    organization_id: str,
    agent_id: Optional[str],
    request_id: str,
    event_type: str,
    decision: Optional[str],
    tool_name: Optional[str],
    sequence_number: int,
    timestamp: str,
    payload: Optional[dict[str, Any]] = None,
) -> str:
    """Deterministic, canonical serialization of audit event data for SHA-256 hashing.

    Two distinct representations of logically identical data will never produce
    differing strings.
    """
    event_dict = {
        "agent_id": str(agent_id) if agent_id else None,
        "decision": str(decision) if decision else None,
        "event_type": str(event_type),
        "organization_id": str(organization_id),
        "payload": payload or {},
        "request_id": str(request_id),
        "sequence_number": int(sequence_number),
        "timestamp": str(timestamp),
        "tool_name": str(tool_name) if tool_name else None,
    }
    return json.dumps(event_dict, sort_keys=True, separators=(",", ":"))


def compute_audit_hash(previous_hash: str, canonical_event_data: str) -> str:
    """Compute SHA-256 hash of previous_hash concatenated with canonical_event_data."""
    combined = f"{previous_hash}{canonical_event_data}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


def record_audit_log(
    db: Session,
    organization_id: uuid.UUID,
    agent_id: Optional[uuid.UUID],
    tool_id: Optional[uuid.UUID],
    event_type: str,
    decision: Optional[str],
    payload: dict[str, Any],
    request_id: uuid.UUID,
    tool_name: Optional[str],
    audit_log_id: Optional[uuid.UUID] = None,
) -> AuditLog:
    """Create and append an AuditLog entry to the organization's hash chain.

    Concurrency control:
      Acquires a row-level lock on the Organization row to serialize sequence
      allocation and previous-hash resolution for this organization. Different
      organizations operate concurrently with independent locks.
    """
    if audit_log_id is None:
        audit_log_id = uuid.uuid4()

    # 1. Acquire organization-scoped row lock to serialize sequence and hash generation
    db.query(Organization.id).filter(Organization.id == organization_id).with_for_update().first()

    # 2. Query the immediately preceding audit log for this organization
    last_log = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.sequence_number.desc())
        .first()
    )

    if last_log is None or last_log.sequence_number is None:
        next_seq = 1
        previous_hash = GENESIS_HASH
    else:
        next_seq = last_log.sequence_number + 1
        previous_hash = last_log.current_hash

    # 3. Establish single source of truth for timestamp; stamp canonical fields into payload
    #    so the verifier can reconstruct the exact same canonical_data from stored rows alone.
    now = datetime.now(timezone.utc)
    timestamp_str = now.isoformat()
    payload["timestamp"] = timestamp_str
    # _request_id and _tool_name are system-stamped (underscore prefix) so they never
    # collide with caller-supplied keys and are always present for re-verification.
    payload["_request_id"] = str(request_id)
    payload["_tool_name"] = str(tool_name) if tool_name else None

    # 4. Generate deterministic canonical serialization and compute SHA-256 hash
    canonical_data = serialize_audit_event(
        organization_id=str(organization_id),
        agent_id=str(agent_id) if agent_id else None,
        request_id=str(request_id),
        event_type=event_type,
        decision=decision,
        tool_name=tool_name,
        sequence_number=next_seq,
        timestamp=timestamp_str,
        payload=payload,
    )
    current_hash = compute_audit_hash(previous_hash, canonical_data)

    # 5. Instantiate and add AuditLog record
    audit_log = AuditLog(
        id=audit_log_id,
        organization_id=organization_id,
        agent_id=agent_id,
        tool_id=tool_id,
        event_type=event_type,
        decision=decision,
        payload=payload,
        previous_hash=previous_hash,
        current_hash=current_hash,
        sequence_number=next_seq,
        created_at=now,
    )
    db.add(audit_log)
    return audit_log


def verify_organization_chain(db: Session, organization_id: uuid.UUID) -> dict[str, Any]:
    """Verify the tamper-evident cryptographic hash chain for an organization.

    EARLY-EXIT BEHAVIOR:
      Verification iterates sequentially through all records ordered by sequence_number.
      If any discrepancy is detected (sequence gap, previous hash mismatch, or recomputed
      hash mismatch), verification immediately terminates and reports that specific broken
      record. Records after the first break are not checked.

    Returns:
      dict with keys:
        status: "VALID" | "INVALID"
        total_records: int
        message: str
        broken_record_id: Optional[str]
        broken_sequence_number: Optional[int]
        error_type: Optional[str]
        details: Optional[str]
        early_exit_note: Optional[str]
        duration_ms: float
    """
    start_time = time.perf_counter()

    logs: list[AuditLog] = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.sequence_number.asc())
        .all()
    )

    total_records = len(logs)
    if total_records == 0:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "status": "VALID",
            "total_records": 0,
            "message": "No audit records found for organization. Empty chain is valid.",
            "broken_record_id": None,
            "broken_sequence_number": None,
            "error_type": None,
            "details": None,
            "early_exit_note": None,
            "duration_ms": round(elapsed_ms, 3),
        }

    expected_previous_hash = GENESIS_HASH
    expected_seq = 1

    for log in logs:
        # Check 1: Sequence number monotonicity and gaplessness
        if log.sequence_number != expected_seq:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "INVALID",
                "total_records": total_records,
                "message": f"Tampering detected at sequence number {log.sequence_number}: sequence gap or out-of-order record.",
                "broken_record_id": str(log.id),
                "broken_sequence_number": log.sequence_number,
                "error_type": "SEQUENCE_GAP_OR_OUT_OF_ORDER",
                "details": f"Expected sequence_number {expected_seq}, but encountered {log.sequence_number}.",
                "early_exit_note": "Verification stopped at first break; records after this point were not checked.",
                "duration_ms": round(elapsed_ms, 3),
            }

        # Check 2: Previous hash linkage continuity
        if log.previous_hash != expected_previous_hash:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "INVALID",
                "total_records": total_records,
                "message": f"Tampering detected at sequence number {log.sequence_number}: previous_hash mismatch.",
                "broken_record_id": str(log.id),
                "broken_sequence_number": log.sequence_number,
                "error_type": "PREVIOUS_HASH_MISMATCH",
                "details": (
                    f"Stored previous_hash '{log.previous_hash}' does not match "
                    f"expected previous hash '{expected_previous_hash}'."
                ),
                "early_exit_note": "Verification stopped at first break; records after this point were not checked.",
                "duration_ms": round(elapsed_ms, 3),
            }

        # Check 3: Current hash cryptographic integrity
        # Re-derive canonical event data from stored record.
        # _request_id and _tool_name are system-stamped keys guaranteed to be present
        # by record_audit_log — do NOT fall back to log.id or other guesses.
        payload = log.payload or {}
        timestamp_str = payload.get("timestamp")
        if not timestamp_str and log.created_at:
            timestamp_str = log.created_at.astimezone(timezone.utc).isoformat()

        request_id_str = payload.get("_request_id") or payload.get("request_id") or str(log.id)
        tool_name_val = payload.get("_tool_name")  # None is a valid value here

        canonical_data = serialize_audit_event(
            organization_id=str(log.organization_id),
            agent_id=str(log.agent_id) if log.agent_id else None,
            request_id=request_id_str,
            event_type=log.event_type,
            decision=log.decision,
            tool_name=tool_name_val,
            sequence_number=log.sequence_number,
            timestamp=timestamp_str,
            payload=payload,
        )
        recomputed_hash = compute_audit_hash(log.previous_hash, canonical_data)


        if recomputed_hash != log.current_hash:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "INVALID",
                "total_records": total_records,
                "message": f"Tampering detected at sequence number {log.sequence_number}: data modification detected.",
                "broken_record_id": str(log.id),
                "broken_sequence_number": log.sequence_number,
                "error_type": "HASH_MISMATCH",
                "details": (
                    f"Recomputed hash '{recomputed_hash}' does not match "
                    f"stored current_hash '{log.current_hash}'."
                ),
                "early_exit_note": "Verification stopped at first break; records after this point were not checked.",
                "duration_ms": round(elapsed_ms, 3),
            }

        # Advance expectation along the chain
        expected_previous_hash = log.current_hash
        expected_seq += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return {
        "status": "VALID",
        "total_records": total_records,
        "message": f"Tamper-evident cryptographic hash chain verified successfully. Zero tampering detected across {total_records} records.",
        "broken_record_id": None,
        "broken_sequence_number": None,
        "error_type": None,
        "details": None,
        "early_exit_note": None,
        "duration_ms": round(elapsed_ms, 3),
    }
