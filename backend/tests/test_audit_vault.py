"""Phase 8 - Cryptographic Audit Vault: Integration Test Suite.

Tests run against a real Postgres instance (TEST_DATABASE_URL env var) to exercise
Postgres-level row locking, JSON serialization, and hash-chain integrity.

Test inventory:
  1.  Empty chain -> VALID
  2.  Single-record chain -> VALID, GENESIS previous_hash, real 64-char hex current_hash
  3.  Multi-record chain (N=5) -> VALID, each link correct
  4.  Payload mutation -> INVALID (HASH_MISMATCH at mutated record)
  5.  current_hash mutation -> INVALID (HASH_MISMATCH at seq=1 or PREVIOUS_HASH_MISMATCH at seq=2)
  6.  previous_hash mutation -> INVALID (PREVIOUS_HASH_MISMATCH at mutated record)
  7.  Sequence gap (deleted intermediate record) -> INVALID (SEQUENCE_GAP_OR_OUT_OF_ORDER)
  8.  Cross-org isolation: two orgs each build independent valid chains; each verifies VALID
  9.  Concurrency: 10 threads x separate DB sessions -> gapless sequence 1..10
 10.  1,000-record chain -> VALID, duration measured and reported
 11.  RBAC: AUDITOR/ADMIN can GET /audit and POST /audit/verify
 12.  RBAC: OPERATOR role receives 403 from /audit and /audit/verify
"""
import hashlib
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.services.audit_vault import (
    GENESIS_HASH,
    compute_audit_hash,
    record_audit_log,
    serialize_audit_event,
    verify_organization_chain,
)

POSTGRES_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://agentguard:agentguard_password@localhost:5432/agentguard",
)


def _make_pg_engine():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    return engine


def _fresh_org(session: Session) -> Organization:
    org = Organization(name=f"AuditTest-{uuid.uuid4().hex[:8]}", slug=f"audit-{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()
    return org


def _write_record(session: Session, org_id: uuid.UUID, seq_hint: int = 0, payload_extra: Optional[dict] = None) -> AuditLog:
    payload = {"info": f"event-{seq_hint}", **(payload_extra or {})}
    return record_audit_log(
        db=session,
        organization_id=org_id,
        agent_id=None,
        tool_id=None,
        event_type="TOOL_REQUEST_EVALUATED",
        decision="ALLOW",
        payload=payload,
        request_id=uuid.uuid4(),
        tool_name="test_tool",
    )


@pytest.fixture(scope="module")
def pg_engine():
    engine = _make_pg_engine()
    yield engine


@pytest.fixture()
def pg_session(pg_engine):
    conn = pg_engine.connect()
    txn = conn.begin()
    SessionLocal = sessionmaker(bind=conn, expire_on_commit=False)
    session = SessionLocal()
    try:
        session.begin_nested()
    except Exception:
        pass
    yield session
    session.close()
    if txn.is_active:
        txn.rollback()
    conn.close()


# ---------------------------------------------------------------------------
# HTTP-layer helpers
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient
from app.core.database import get_db
from app.main import app as fastapi_app


def _http_client_for_session(session: Session) -> TestClient:
    def override_get_db():
        try:
            yield session
        finally:
            pass
    fastapi_app.dependency_overrides[get_db] = override_get_db
    return TestClient(fastapi_app, raise_server_exceptions=True)


def _register_and_login(client: TestClient, role: str = "ADMIN") -> dict:
    slug = f"rbac-{uuid.uuid4().hex[:6]}"
    email = f"{uuid.uuid4().hex[:6]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password1!", "organization_slug": slug, "role": role},
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    r2 = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password1!", "organization_slug": slug},
    )
    assert r2.status_code == 200, f"Login failed: {r2.text}"
    token = r2.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Hash chain logic tests
# ===========================================================================
class TestAuditVaultHashChain:
    def test_empty_chain_is_valid(self, pg_session):
        """1. Organisation with no audit records reports VALID."""
        org = _fresh_org(pg_session)
        pg_session.commit()
        result = verify_organization_chain(pg_session, org.id)
        assert result["status"] == "VALID"
        assert result["total_records"] == 0
        assert result["broken_record_id"] is None

    def test_single_record_valid(self, pg_session):
        """2. One record chains from GENESIS_HASH with a real 64-char hex current_hash."""
        org = _fresh_org(pg_session)
        log = _write_record(pg_session, org.id, seq_hint=1)
        pg_session.commit()

        assert log.sequence_number == 1
        assert log.previous_hash == GENESIS_HASH
        assert re.fullmatch(r"[0-9a-f]{64}", log.current_hash), "current_hash must be 64-char hex"
        assert log.current_hash != GENESIS_HASH

        result = verify_organization_chain(pg_session, org.id)
        assert result["status"] == "VALID"
        assert result["total_records"] == 1

    def test_multi_record_chain_valid(self, pg_session):
        """3. N=5 sequential records form a correctly linked chain."""
        org = _fresh_org(pg_session)
        logs = [_write_record(pg_session, org.id, seq_hint=i) for i in range(5)]
        pg_session.commit()

        assert [l.sequence_number for l in logs] == list(range(1, 6))
        assert logs[0].previous_hash == GENESIS_HASH
        for i in range(1, 5):
            assert logs[i].previous_hash == logs[i - 1].current_hash, (
                f"Link broken at seq {logs[i].sequence_number}"
            )

        result = verify_organization_chain(pg_session, org.id)
        assert result["status"] == "VALID"
        assert result["total_records"] == 5
        assert isinstance(result["duration_ms"], float)

    def test_payload_mutation_detected(self, pg_session):
        """4. Mutating payload after commit causes HASH_MISMATCH at mutated record."""
        org = _fresh_org(pg_session)
        logs = [_write_record(pg_session, org.id, seq_hint=i) for i in range(3)]
        pg_session.commit()

        target = logs[1]
        pg_session.execute(
            sqlalchemy.text(
                "UPDATE audit_logs SET payload = jsonb_set(payload::jsonb, '{info}', '\"TAMPERED\"') WHERE id = :id"
            ),
            {"id": str(target.id)},
        )
        pg_session.expire(target)

        result = verify_organization_chain(pg_session, org.id)
        assert result["status"] == "INVALID"
        assert result["error_type"] == "HASH_MISMATCH"
        assert result["broken_sequence_number"] == 2
        assert result["broken_record_id"] == str(target.id)
        assert result["early_exit_note"] is not None

    def test_current_hash_mutation_detected(self, pg_session):
        """5. Mutating current_hash of record N is detected as HASH_MISMATCH or PREVIOUS_HASH_MISMATCH."""
        org = _fresh_org(pg_session)
        logs = [_write_record(pg_session, org.id, seq_hint=i) for i in range(3)]
        pg_session.commit()

        pg_session.execute(
            sqlalchemy.text("UPDATE audit_logs SET current_hash = :fake WHERE id = :id"),
            {"fake": "a" * 64, "id": str(logs[0].id)},
        )
        pg_session.expire(logs[0])

        result = verify_organization_chain(pg_session, org.id)
        assert result["status"] == "INVALID"
        assert result["error_type"] in ("HASH_MISMATCH", "PREVIOUS_HASH_MISMATCH")
        assert result["broken_sequence_number"] in (1, 2)

    def test_previous_hash_mutation_detected(self, pg_session):
        """6. Mutating previous_hash causes PREVIOUS_HASH_MISMATCH at that record."""
        org = _fresh_org(pg_session)
        logs = [_write_record(pg_session, org.id, seq_hint=i) for i in range(3)]
        pg_session.commit()

        pg_session.execute(
            sqlalchemy.text("UPDATE audit_logs SET previous_hash = :fake WHERE id = :id"),
            {"fake": "b" * 64, "id": str(logs[2].id)},
        )
        pg_session.expire(logs[2])

        result = verify_organization_chain(pg_session, org.id)
        assert result["status"] == "INVALID"
        assert result["error_type"] == "PREVIOUS_HASH_MISMATCH"
        assert result["broken_sequence_number"] == 3

    def test_sequence_gap_detected(self, pg_session):
        """7. Deleting an intermediate record causes SEQUENCE_GAP_OR_OUT_OF_ORDER."""
        org = _fresh_org(pg_session)
        logs = [_write_record(pg_session, org.id, seq_hint=i) for i in range(4)]
        pg_session.commit()

        pg_session.execute(
            sqlalchemy.text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": str(logs[1].id)},
        )

        result = verify_organization_chain(pg_session, org.id)
        assert result["status"] == "INVALID"
        assert result["error_type"] == "SEQUENCE_GAP_OR_OUT_OF_ORDER"
        assert result["broken_sequence_number"] == 3

    def test_cross_org_isolation(self, pg_session):
        """8. Two orgs build independent chains; each verifies as VALID independently."""
        org_a = _fresh_org(pg_session)
        org_b = _fresh_org(pg_session)

        for i in range(5):
            _write_record(pg_session, org_a.id, seq_hint=i)
        for i in range(3):
            _write_record(pg_session, org_b.id, seq_hint=i)
        pg_session.commit()

        result_a = verify_organization_chain(pg_session, org_a.id)
        result_b = verify_organization_chain(pg_session, org_b.id)

        assert result_a["status"] == "VALID", f"Org A invalid: {result_a}"
        assert result_a["total_records"] == 5
        assert result_b["status"] == "VALID", f"Org B invalid: {result_b}"
        assert result_b["total_records"] == 3


# ===========================================================================
# Concurrency test - separate DB connections per thread
# ===========================================================================
class TestAuditVaultConcurrency:
    def test_concurrent_writes_produce_gapless_sequence(self, pg_engine):
        """9. 10 concurrent threads, each with its OWN session/connection, produce
        gapless sequences 1..10 and a VALID chain.

        Using per-thread sessions ensures the test exercises Postgres-level FOR UPDATE
        row locking, not Python GIL or SQLAlchemy session-level serialisation.
        """
        N_THREADS = 10

        # Create org in a dedicated session that fully commits before threads start
        setup_session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
        org = Organization(
            name=f"ConcurrencyOrg-{uuid.uuid4().hex[:8]}",
            slug=f"conc-{uuid.uuid4().hex[:8]}",
        )
        setup_session.add(org)
        setup_session.commit()
        org_id = org.id
        setup_session.close()

        errors: list[str] = []

        def write_one_record(thread_index: int) -> Optional[int]:
            # Each thread opens its own engine connection (separate Postgres backend session)
            thread_session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
            try:
                log = record_audit_log(
                    db=thread_session,
                    organization_id=org_id,
                    agent_id=None,
                    tool_id=None,
                    event_type="TOOL_REQUEST_EVALUATED",
                    decision="ALLOW",
                    payload={"thread": thread_index},
                    request_id=uuid.uuid4(),
                    tool_name="concurrent_tool",
                )
                thread_session.commit()
                return log.sequence_number
            except Exception as exc:
                errors.append(f"Thread {thread_index} failed: {exc}")
                thread_session.rollback()
                return None
            finally:
                thread_session.close()

        with ThreadPoolExecutor(max_workers=N_THREADS) as pool:
            futures = [pool.submit(write_one_record, i) for i in range(N_THREADS)]
            seq_numbers = [f.result() for f in as_completed(futures)]

        assert not errors, f"Thread errors: {errors}"
        assert None not in seq_numbers, "Some threads failed to write"

        seq_sorted = sorted(seq_numbers)
        assert seq_sorted == list(range(1, N_THREADS + 1)), (
            f"Expected gapless 1..{N_THREADS}, got {seq_sorted}"
        )

        verify_session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
        try:
            result = verify_organization_chain(verify_session, org_id)
            assert result["status"] == "VALID", f"Chain invalid after concurrent writes: {result}"
            assert result["total_records"] == N_THREADS
        finally:
            verify_session.close()


# ===========================================================================
# Scale tests
# ===========================================================================
class TestAuditVaultScale:
    def test_thousand_record_chain_valid(self, pg_engine):
        """10. 1,000 sequential records: chain VALID, duration measured."""
        N = 1_000
        session = sessionmaker(bind=pg_engine, expire_on_commit=False)()

        org = Organization(
            name=f"ScaleOrg-{uuid.uuid4().hex[:8]}",
            slug=f"scale-{uuid.uuid4().hex[:8]}",
        )
        session.add(org)
        session.flush()

        for i in range(N):
            record_audit_log(
                db=session,
                organization_id=org.id,
                agent_id=None,
                tool_id=None,
                event_type="TOOL_REQUEST_EVALUATED",
                decision="ALLOW",
                payload={"seq_hint": i, "data": "x" * 64},
                request_id=uuid.uuid4(),
                tool_name="scale_tool",
            )
            if (i + 1) % 100 == 0:
                session.commit()

        session.commit()

        t0 = time.perf_counter()
        result = verify_organization_chain(session, org.id)
        wall_ms = (time.perf_counter() - t0) * 1000.0

        session.close()

        assert result["status"] == "VALID", f"1,000-record chain invalid: {result}"
        assert result["total_records"] == N

        print(
            f"\n[Phase 8 Scale] Verified {N} records in {wall_ms:.1f} ms "
            f"(service-reported: {result['duration_ms']:.1f} ms)"
        )
        assert wall_ms < 30_000, f"Verification took {wall_ms:.0f} ms - unexpectedly slow"

    def test_tampering_pinpointed_in_large_chain(self, pg_engine):
        """10b. Tamper at record #250 of a 500-record chain; exact record is pinpointed."""
        N = 500
        TAMPER_SEQ = 250
        session = sessionmaker(bind=pg_engine, expire_on_commit=False)()

        org = Organization(
            name=f"TamperOrg-{uuid.uuid4().hex[:8]}",
            slug=f"tamper-{uuid.uuid4().hex[:8]}",
        )
        session.add(org)
        session.flush()

        target_id = None
        for i in range(N):
            log = record_audit_log(
                db=session,
                organization_id=org.id,
                agent_id=None,
                tool_id=None,
                event_type="TOOL_REQUEST_EVALUATED",
                decision="ALLOW",
                payload={"seq_hint": i},
                request_id=uuid.uuid4(),
                tool_name="scale_tool",
            )
            if log.sequence_number == TAMPER_SEQ:
                target_id = log.id
            if (i + 1) % 100 == 0:
                session.commit()

        session.commit()
        assert target_id is not None

        session.execute(
            sqlalchemy.text(
                "UPDATE audit_logs SET payload = jsonb_set(payload::jsonb, '{seq_hint}', '9999') WHERE id = :id"
            ),
            {"id": str(target_id)},
        )

        result = verify_organization_chain(session, org.id)
        session.close()

        assert result["status"] == "INVALID"
        assert result["broken_sequence_number"] == TAMPER_SEQ
        assert result["broken_record_id"] == str(target_id)
        assert result["error_type"] == "HASH_MISMATCH"
        assert result["early_exit_note"] is not None


# ===========================================================================
# RBAC tests
# ===========================================================================
class TestAuditVaultRBAC:
    def test_auditor_can_list_audit_logs(self, pg_session):
        """11a. AUDITOR role can GET /audit."""
        client = _http_client_for_session(pg_session)
        try:
            headers = _register_and_login(client, role="AUDITOR")
            r = client.get("/api/v1/audit", headers=headers)
            assert r.status_code == 200, r.text
            body = r.json()
            assert "items" in body
            assert "total" in body
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_auditor_can_trigger_verify(self, pg_session):
        """11b. AUDITOR role can POST /audit/verify."""
        client = _http_client_for_session(pg_session)
        try:
            headers = _register_and_login(client, role="AUDITOR")
            r = client.post("/api/v1/audit/verify", headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "VALID"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_admin_can_trigger_verify(self, pg_session):
        """11c. ADMIN role can POST /audit/verify."""
        client = _http_client_for_session(pg_session)
        try:
            headers = _register_and_login(client, role="ADMIN")
            r = client.post("/api/v1/audit/verify", headers=headers)
            assert r.status_code == 200, r.text
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_developer_forbidden_from_audit_list(self, pg_session):
        """12a. DEVELOPER role receives 403 from GET /audit."""
        client = _http_client_for_session(pg_session)
        try:
            headers = _register_and_login(client, role="DEVELOPER")
            r = client.get("/api/v1/audit", headers=headers)
            assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_developer_forbidden_from_verify(self, pg_session):
        """12b. DEVELOPER role receives 403 from POST /audit/verify."""
        client = _http_client_for_session(pg_session)
        try:
            headers = _register_and_login(client, role="DEVELOPER")
            r = client.post("/api/v1/audit/verify", headers=headers)
            assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_unauthenticated_request_rejected(self, pg_session):
        """Unauthenticated requests return 401."""
        client = _http_client_for_session(pg_session)
        try:
            r1 = client.get("/api/v1/audit")
            assert r1.status_code == 401
            r2 = client.post("/api/v1/audit/verify")
            assert r2.status_code == 401
        finally:
            fastapi_app.dependency_overrides.clear()


# ===========================================================================
# Canonical serialization unit tests (no DB needed)
# ===========================================================================
class TestCanonicalSerialization:
    def test_same_args_produce_identical_string(self):
        """serialize_audit_event is deterministic."""
        kwargs = dict(
            organization_id="aaaaaaaa-0000-0000-0000-000000000000",
            agent_id="bbbbbbbb-0000-0000-0000-000000000000",
            request_id="cccccccc-0000-0000-0000-000000000000",
            event_type="TOOL_REQUEST_EVALUATED",
            decision="ALLOW",
            tool_name="read_customer",
            sequence_number=42,
            timestamp="2024-01-01T00:00:00+00:00",
            payload={"z": 1, "a": 2},
        )
        assert serialize_audit_event(**kwargs) == serialize_audit_event(**kwargs)

    def test_payload_key_order_does_not_matter(self):
        """sort_keys=True means key insertion order has no effect."""
        base = dict(
            organization_id="aaaaaaaa-0000-0000-0000-000000000000",
            agent_id=None,
            request_id="cccccccc-0000-0000-0000-000000000000",
            event_type="TOOL_REQUEST_EVALUATED",
            decision="DENY",
            tool_name=None,
            sequence_number=1,
            timestamp="2024-01-01T00:00:00+00:00",
        )
        s1 = serialize_audit_event(**base, payload={"a": 1, "b": 2})
        s2 = serialize_audit_event(**base, payload={"b": 2, "a": 1})
        assert s1 == s2

    def test_compute_audit_hash_returns_64_char_hex(self):
        h = compute_audit_hash("0" * 64, '{"test":true}')
        assert len(h) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", h)

    def test_genesis_chain_hash_matches_manual_computation(self):
        canonical = '{"key":"value"}'
        combined = (GENESIS_HASH + canonical).encode("utf-8")
        expected = hashlib.sha256(combined).hexdigest()
        assert compute_audit_hash(GENESIS_HASH, canonical) == expected
