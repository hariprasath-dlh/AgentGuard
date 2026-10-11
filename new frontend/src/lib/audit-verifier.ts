export interface AuditVerificationBackendResponse {
  status: string;
  total_records: number;
  message: string;
  broken_record_id?: string | null;
  broken_sequence_number?: number | null;
  error_type?: string | null;
  details?: string | null;
  early_exit_note?: string | null;
  duration_ms?: number | null;
}

export interface ParsedVerification {
  isValid: boolean;
  totalRecords: number;
  message: string;
  brokenSequenceNumber: number | null;
}

export function parseAuditVerification(raw: AuditVerificationBackendResponse): ParsedVerification {
  const isValid = raw.status === "VALID";
  return {
    isValid,
    totalRecords: raw.total_records,
    message: raw.message,
    brokenSequenceNumber: isValid ? null : (raw.broken_sequence_number ?? null),
  };
}
