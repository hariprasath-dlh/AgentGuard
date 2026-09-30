/**
 * AgentGuard Data Layer (Connected to real FastAPI backend).
 *
 * Dispatches API requests directly to the FastAPI REST endpoints at
 * http://localhost:8000/api/v1 using standard Bearer token authentication.
 */

export const API_BASE_URL =
  typeof window !== "undefined" && (window as unknown as { __AGENTGUARD_API_URL__?: string }).__AGENTGUARD_API_URL__
    ? (window as unknown as { __AGENTGUARD_API_URL__?: string }).__AGENTGUARD_API_URL__!
    : "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
};

/** Fired on any auth failure so the auth context can clear state and redirect. */
export const UNAUTHORIZED_EVENT = "agentguard:unauthorized";

function unauthorized(): never {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
  }
  throw new ApiError("Session expired. Please log in again.", 401);
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { method = "GET", body } = options;
  const token = typeof window !== "undefined" ? localStorage.getItem("agentguard_token") : null;

  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: Record<string, string> = {};

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const fetchInit: RequestInit = {
    method,
    headers,
  };
  if (body !== undefined) {
    fetchInit.body = JSON.stringify(body);
  }
  if (options.signal) {
    fetchInit.signal = options.signal;
  }

  const res = await fetch(url, fetchInit);

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("agentguard_token");
    }
    unauthorized();
  }

  if (!res.ok) {
    let errorMsg = `Request failed (${res.status})`;
    try {
      const errorJson = await res.json();
      if (Array.isArray(errorJson.detail)) {
        errorMsg = errorJson.detail
          .map((d: { msg?: string; message?: string }) => d.msg || d.message || JSON.stringify(d))
          .join("; ");
      } else if (typeof errorJson.detail === "string") {
        errorMsg = errorJson.detail;
      } else if (errorJson.message) {
        errorMsg = errorJson.message;
      }
    } catch {
      // ignore non-json error bodies
    }
    throw new ApiError(errorMsg, res.status);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

/* ---------------------------------- types --------------------------------- */

export type Role = "ADMIN" | "SECURITY" | "AUDITOR" | "MANAGER" | "DEVELOPER";

export type Me = {
  id: string;
  email: string;
  full_name?: string | null;
  role: Role;
  organization?: {
    id?: string;
    name?: string;
    slug?: string;
  } | null;
  organization_id?: string;
  organization_name?: string;
  organization_slug?: string;
};

export type Agent = {
  id: string;
  name: string;
  description?: string | null;
  status?: string | null;
  created_at?: string | null;
  api_key?: string | null;
  api_key_prefix?: string | null;
};

export type Tool = {
  id: string;
  name: string;
  description?: string | null;
  risk_level?: string | null;
  is_active?: boolean | null;
  created_at?: string | null;
};

export type Permission = {
  id?: string;
  agent_id: string;
  tool_id: string;
  is_allowed?: boolean | null;
  max_calls_per_day?: number | null;
};

export type Policy = {
  id: string;
  name: string;
  description?: string | null;
  policy_type?: string | null;
  rules?: Record<string, unknown> | null;
  is_active?: boolean | null;
};

export type Budget = {
  id: string;
  agent_id: string;
  max_requests_per_minute?: number | null;
  max_requests_per_day?: number | null;
  max_budget_per_session?: number | null;
  max_budget_per_day?: number | null;
  current_spend?: number | null;
};

export type HitlRequest = {
  id: string;
  agent_id: string;
  tool_name?: string | null;
  tool_id?: string | null;
  risk_level?: string | null;
  status?: string | null;
  reason?: string | null;
  parameters?: Record<string, unknown> | null;
  input_payload?: Record<string, unknown> | null;
  output_payload?: Record<string, unknown> | null;
  requested_at?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
  review_notes?: string | null;
  reviewed_at?: string | null;
};

export type AuditLog = {
  id: string;
  sequence_number: number;
  timestamp?: string | null;
  created_at?: string | null;
  event_type?: string | null;
  decision?: string | null;
  current_hash: string;
  previous_hash?: string | null;
  event_data?: Record<string, unknown> | null;
};

export type ChainVerification = {
  status: "VALID" | "INVALID";
  total_records: number;
  message: string;
  broken_record_id?: string | null;
  broken_sequence_number?: number | null;
  error_type?: string | null;
  error?: string | null;
  details?: string | null;
  early_exit_note?: string | null;
  duration_ms?: number;
  records_verified?: number;
  verified_at?: string | null;
};

export type DashboardStats = {
  total_agents?: number;
  total_tools?: number;
  requests_today?: number;
  allowed_today?: number;
  blocked_today?: number;
  pending_today?: number;
  total_spend_today?: number;
  budget_utilization?: Array<{
    agent_id: string;
    agent_name?: string | null;
    daily_cost?: number | null;
    daily_limit?: number | null;
    utilization_percent?: number | null;
  }>;
};

export type ActivityItem = {
  id: string;
  timestamp?: string | null;
  created_at?: string | null;
  agent_id?: string | null;
  agent_name?: string | null;
  tool_name?: string | null;
  decision?: string | null;
  reason?: string | null;
  latency_ms?: number | null;
  payload?: Record<string, unknown> | null;
};

/** Endpoints may return either a bare array or a paginated envelope. */
export function asList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === "object") {
    const p = payload as Record<string, unknown>;
    for (const key of ["items", "results", "data", "logs", "activity", "requests"]) {
      if (Array.isArray(p[key])) return p[key] as T[];
    }
  }
  return [];
}
