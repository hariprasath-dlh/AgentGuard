# Audit Vault

This document describes the SHA-256 hash-chain audit system implemented in AgentGuard.

---

## Language Discipline

Throughout this document and the entire AgentGuard system, the audit log is described as **tamper-evident, not tamper-proof**.

- **Tamper-evident:** The system detects tampering after the fact by verifying cryptographic linkage. If any record has been modified, inserted, or deleted, the verification algorithm identifies the exact point of discontinuity.
- **Not tamper-proof:** An actor with direct database write access can still modify records. The hash chain does not *prevent* this — it *detects* it. The system is a single-application chain, not a distributed consensus ledger.

This distinction matters for regulatory claims. AgentGuard does not claim to prevent tampering; it provides a mechanism to prove whether tampering occurred.

---

## Hash-Chain Design

### Canonical Event Serialization

Every audit event is serialized to a deterministic UTF-8 JSON string before hashing:

```python
event_dict = {
    "agent_id": str(agent_id) or None,
    "decision": str(decision) or None,
    "event_type": str(event_type),
    "organization_id": str(organization_id),
    "payload": payload or {},
    "request_id": str(request_id),
    "sequence_number": int(sequence_number),
    "timestamp": str(timestamp),    # ISO 8601 UTC
    "tool_name": str(tool_name) or None,
}
canonical_data = json.dumps(event_dict, sort_keys=True, separators=(",", ":"))
```

Key properties:
- **Sorted keys** — `sort_keys=True` ensures deterministic key ordering
- **Compact separators** — `separators=(",", ":")` with zero extraneous whitespace
- **Single timestamp source** — the timestamp in the canonical data is the same one stored in the payload, established at write time
- **Nine canonical fields** — organization_id, agent_id, request_id, event_type, decision, tool_name, sequence_number, timestamp, payload

Two distinct representations of logically identical data will never produce differing canonical strings.

### Hash Computation

```
current_hash = SHA256(previous_hash + canonical_event_data)
```

Where:
- `previous_hash` is the `current_hash` of the immediately preceding record in the organization's chain
- `canonical_event_data` is the deterministic JSON string defined above
- The concatenation is `f"{previous_hash}{canonical_event_data}".encode("utf-8")`
- The hash is a lowercase hex digest (64 characters)

### Genesis Hash

The first record in each organization's chain uses a genesis hash of 64 zero characters:

```
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
```

This establishes the chain anchor. There is no special "genesis record" — the first audit log entry simply uses this value as its `previous_hash`.

---

## Per-Organization Chain Isolation

Each organization has its own independent hash chain:
- **Sequence numbers** are monotonic and gapless within each organization, starting at 1
- **Previous hashes** link only to records within the same organization
- **Verification** operates on a single organization's chain at a time

Different organizations' chains are completely independent. There is no cross-organization hash linkage.

---

## Concurrency Control and the Throughput Tradeoff

### The Problem

Under concurrent requests, two guard evaluations for the same organization might try to allocate the same sequence number or read stale `previous_hash` values, producing a forked or corrupted chain.

### The Solution

The `record_audit_log` function acquires a **row-level exclusive lock** on the organization row before allocating a sequence number:

```python
# Acquire organization-scoped row lock
db.query(Organization.id).filter(
    Organization.id == organization_id
).with_for_update().first()
```

This `SELECT ... FOR UPDATE` serializes all audit writes within a single organization. The sequence is:

1. Acquire row lock on `organizations` where `id = org_id`
2. Query the last `audit_logs` record for this org (ordered by `sequence_number DESC`)
3. Compute `next_seq = last.sequence_number + 1` (or `1` if no records exist)
4. Set `previous_hash = last.current_hash` (or `GENESIS_HASH`)
5. Serialize, hash, insert the new `audit_logs` record
6. Release lock (on transaction commit)

### The Tradeoff

This design guarantees gapless, monotonic sequence numbers and correct hash chaining, but it **serializes all audit writes within a single organization**. Under high concurrency:

- **Within one organization:** Audit writes are processed one at a time. This is the throughput ceiling for a single organization.
- **Across organizations:** Fully parallel. No lock contention between different organizations.

This is a deliberate tradeoff. The alternative — allowing concurrent writes with gap-filling or optimistic locking — would complicate verification and risk chain integrity. For AgentGuard's governance use case, correctness is more important than write throughput within a single tenant.

> **Note on SQLite:** The `SELECT ... FOR UPDATE` locking is a PostgreSQL feature. When running with SQLite (local development), the lock is a no-op. This means SQLite can produce sequence number races under concurrent requests. PostgreSQL is required for production correctness.

---

## Verification Algorithm

The `verify_organization_chain` function validates the entire chain:

```
1. Load all audit_logs for the organization, ordered by sequence_number ASC
2. Set expected_previous_hash = GENESIS_HASH, expected_seq = 1
3. For each record:
   a. Check sequence_number == expected_seq (gapless monotonicity)
   b. Check previous_hash == expected_previous_hash (chain linkage)
   c. Re-derive canonical_event_data from stored record fields
   d. Recompute hash = SHA256(previous_hash + canonical_event_data)
   e. Check recomputed hash == stored current_hash (data integrity)
   f. If any check fails: RETURN INVALID immediately (early exit)
   g. Set expected_previous_hash = current_hash, expected_seq += 1
4. If all records pass: RETURN VALID
```

### Early-Exit Behavior

Verification stops at the **first detected discontinuity** and reports that specific broken record. Records after the first break are not checked. This is documented in the response:

```json
{
  "early_exit_note": "Verification stopped at first break; records after this point were not checked."
}
```

### Three Types of Detected Tampering

| Error Type | Detection | Meaning |
|-----------|-----------|---------|
| `SEQUENCE_GAP_OR_OUT_OF_ORDER` | `sequence_number != expected_seq` | A record was deleted or inserted out of sequence |
| `PREVIOUS_HASH_MISMATCH` | `previous_hash != expected_previous_hash` | A record was inserted or the preceding record was modified |
| `HASH_MISMATCH` | Recomputed hash ≠ stored `current_hash` | The record's data was modified after it was written |

### Verification Response Shape

```json
{
  "status": "VALID",            // or "INVALID"
  "total_records": 20,
  "message": "...",
  "broken_record_id": null,     // UUID of first broken record, or null
  "broken_sequence_number": null, // sequence number of break, or null
  "error_type": null,           // SEQUENCE_GAP_OR_OUT_OF_ORDER | PREVIOUS_HASH_MISMATCH | HASH_MISMATCH
  "details": null,              // human-readable explanation
  "early_exit_note": null,      // present only on INVALID
  "duration_ms": 12.5           // wall-clock verification time
}
```

---

## Payload Metadata Stamping

When `record_audit_log` creates a record, it stamps three system fields into the `payload` JSON column:

| Key | Value | Purpose |
|-----|-------|---------|
| `timestamp` | ISO 8601 UTC string | Canonical timestamp for hash computation |
| `_request_id` | UUID string | Ensures the verifier can reconstruct canonical data |
| `_tool_name` | Tool name or null | Same purpose |

The underscore prefix on `_request_id` and `_tool_name` prevents collisions with caller-supplied keys.

---

## Event Types

The following `event_type` values are written by the system:

| Event Type | When Written | Decision |
|------------|-------------|----------|
| `TOOL_REQUEST_EVALUATED` | Every `POST /guard/check` call | ALLOW, DENY, or PENDING |
| `HITL_APPROVED` | Manager approves a HITL request | APPROVED |
| `HITL_DENIED` | Manager denies a HITL request | DENIED |
| `TOOL_EXECUTED` | Mock handler runs successfully after approval | EXECUTED |
| `TOOL_EXECUTION_FAILED` | Mock handler raises during resume | ERROR |
| `TOOL_EXECUTION_SKIPPED` | No mock handler registered for approved tool | SKIPPED |

---

## Dashboard Integration

The Control Plane's Audit Vault screen (`/audit`) provides:

1. **Log table** — paginated, reverse-chronological list of audit records with sequence numbers, timestamps, event types, decisions, and truncated hash values
2. **Chain visual** — a vertical chain visualization showing the first 12 records with color-coded integrity status
3. **Verify Chain button** — triggers `POST /api/v1/audit/verify` and displays the result with a sweep animation
4. **Hash chips** — clickable hash values that copy the full 64-character hash to clipboard

---

## Limitations

1. **Single-application chain** — the chain is maintained by one application writing to one database. It is not a distributed ledger or blockchain.
2. **No external anchoring** — the chain is not periodically anchored to a public blockchain, certificate transparency log, or timestamping authority. External anchoring would strengthen non-repudiation.
3. **Per-organization lock contention** — high write throughput within a single organization is limited by the row-level lock. This is a correctness-over-throughput tradeoff.
4. **Payload stored in JSON column** — the canonical data is reconstructed from stored fields during verification. If the PostgreSQL JSON serialization were to change behavior (unlikely), verification could produce false positives. The canonical serialization function mitigates this by controlling its own output format.
5. **SQLite doesn't support row locks** — running with SQLite (local dev) provides no concurrency safety for chain writes.
