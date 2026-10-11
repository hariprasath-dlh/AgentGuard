import { describe, expect, it } from "vitest";
import {
  parseAuditVerification,
  type AuditVerificationBackendResponse,
} from "@/lib/audit-verifier";

describe("Audit Verification Response Mapper", () => {
  it("correctly maps a real VALID backend verification response", () => {
    const validSample: AuditVerificationBackendResponse = {
      status: "VALID",
      total_records: 42,
      message: "Audit vault verified successfully. 42 records scanned, hash chain intact.",
      broken_record_id: null,
      broken_sequence_number: null,
      error_type: null,
      details: null,
      early_exit_note: null,
      duration_ms: 12.5,
    };

    const parsed = parseAuditVerification(validSample);
    expect(parsed.isValid).toBe(true);
    expect(parsed.totalRecords).toBe(42);
    expect(parsed.message).toBe(validSample.message);
    expect(parsed.brokenSequenceNumber).toBeNull();
  });

  it("correctly maps a real INVALID backend verification response with broken sequence", () => {
    const invalidSample: AuditVerificationBackendResponse = {
      status: "INVALID",
      total_records: 42,
      message: "Cryptographic hash chain broken at sequence #14: previous hash mismatch.",
      broken_record_id: "550e8400-e29b-41d4-a716-446655440000",
      broken_sequence_number: 14,
      error_type: "HASH_MISMATCH",
      details: "Expected abc..., received def...",
      early_exit_note: "Verification stopped at first discrepancy.",
      duration_ms: 5.2,
    };

    const parsed = parseAuditVerification(invalidSample);
    expect(parsed.isValid).toBe(false);
    expect(parsed.totalRecords).toBe(42);
    expect(parsed.message).toBe(invalidSample.message);
    expect(parsed.brokenSequenceNumber).toBe(14);
  });

  it("strictly enforces status === VALID without fallback to ambiguous fields", () => {
    const edgeSample: AuditVerificationBackendResponse = {
      status: "UNKNOWN_STATUS",
      total_records: 10,
      message: "Ambiguous response",
      broken_sequence_number: null,
    };

    const parsed = parseAuditVerification(edgeSample);
    expect(parsed.isValid).toBe(false);
  });
});
