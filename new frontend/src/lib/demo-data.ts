// DEMO ENVIRONMENT — all records below are mock data for the preview only.
export type Risk = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Decision = "ALLOW" | "DENY" | "PENDING";

export interface Agent {
  id: string;
  name: string;
  description: string;
  status: "ACTIVE" | "SUSPENDED";
  deleted?: boolean;
  apiKey: string;
  keyRevealed: boolean;
  createdAt: string;
}
export interface Tool {
  id: string;
  name: string;
  endpoint: string;
  risk: Risk;
  active: boolean;
  description: string;
}
export interface Permission {
  agentId: string;
  toolId: string;
}
export interface Policy {
  id: string;
  name: string;
  description: string;
  active: boolean;
  config: string;
}
export interface Budget {
  agentId: string;
  dailyCap: number;
  sessionCap: number;
  rpm: number;
  rpd: number;
  spentToday: number;
  requestsToday: number;
}
export interface Approval {
  id: string;
  agentId: string;
  toolId: string;
  status: "PENDING" | "APPROVED" | "DENIED" | "EXPIRED";
  reason: string;
  payload: Record<string, unknown>;
  createdAt: string;
  note?: string;
}
export interface AuditRecord {
  id: number;
  ts: string;
  agentId: string;
  toolId: string;
  decision: Decision;
  reason: string;
  payload: Record<string, unknown>;
  prevHash: string;
  hash: string;
}

const key = () =>
  "ag_demo_" +
  Array.from({ length: 32 }, () => "abcdef0123456789"[Math.floor(Math.random() * 16)]).join("");

export const seedAgents: Agent[] = [
  {
    id: "agt_01",
    name: "Procurement Assistant",
    description: "Places supplier orders under approval.",
    status: "ACTIVE",
    apiKey: key(),
    keyRevealed: false,
    createdAt: "2026-09-02",
  },
  {
    id: "agt_02",
    name: "Support Triage",
    description: "Reads tickets, drafts replies, issues small refunds.",
    status: "ACTIVE",
    apiKey: key(),
    keyRevealed: false,
    createdAt: "2026-09-11",
  },
  {
    id: "agt_03",
    name: "Infra Operator",
    description: "Scales services and rotates non-prod credentials.",
    status: "ACTIVE",
    apiKey: key(),
    keyRevealed: false,
    createdAt: "2026-09-19",
  },
  {
    id: "agt_04",
    name: "Research Crawler",
    description: "Fetches public web pages for summaries.",
    status: "SUSPENDED",
    apiKey: key(),
    keyRevealed: false,
    createdAt: "2026-08-28",
  },
];

export const seedTools: Tool[] = [
  {
    id: "tl_web",
    name: "web.fetch",
    endpoint: "GET https://*",
    risk: "LOW",
    active: true,
    description: "Fetch a public URL.",
  },
  {
    id: "tl_mail",
    name: "email.send",
    endpoint: "POST /mail/send",
    risk: "MEDIUM",
    active: true,
    description: "Send an outbound email.",
  },
  {
    id: "tl_refund",
    name: "payments.refund",
    endpoint: "POST /payments/refund",
    risk: "HIGH",
    active: true,
    description: "Refund a customer charge.",
  },
  {
    id: "tl_order",
    name: "procurement.order",
    endpoint: "POST /orders",
    risk: "HIGH",
    active: true,
    description: "Place a supplier purchase order.",
  },
  {
    id: "tl_scale",
    name: "infra.scale",
    endpoint: "POST /k8s/scale",
    risk: "CRITICAL",
    active: true,
    description: "Change replica counts.",
  },
  {
    id: "tl_legacy",
    name: "crm.export_v1",
    endpoint: "GET /crm/export",
    risk: "MEDIUM",
    active: false,
    description: "Retired bulk export.",
  },
];

export const seedPermissions: Permission[] = [
  { agentId: "agt_01", toolId: "tl_order" },
  { agentId: "agt_01", toolId: "tl_mail" },
  { agentId: "agt_02", toolId: "tl_mail" },
  { agentId: "agt_02", toolId: "tl_refund" },
  { agentId: "agt_03", toolId: "tl_scale" },
  { agentId: "agt_04", toolId: "tl_web" },
];

export const seedPolicies: Policy[] = [
  {
    id: "pol_1",
    name: "Refund ceiling",
    description: "Refunds above $200 require human approval.",
    active: true,
    config: JSON.stringify(
      { tool: "payments.refund", rule: "param.amount > 200", action: "REQUIRE_APPROVAL" },
      null,
      2,
    ),
  },
  {
    id: "pol_2",
    name: "Business hours for infra",
    description: "Deny infra changes outside 08:00–20:00 UTC.",
    active: true,
    config: JSON.stringify(
      { tool: "infra.scale", rule: "time.utc_hour not in [8,20]", action: "DENY" },
      null,
      2,
    ),
  },
  {
    id: "pol_3",
    name: "External domains",
    description: "Block email to non-allowlisted domains.",
    active: false,
    config: JSON.stringify(
      { tool: "email.send", rule: "param.to.domain not in allowlist", action: "DENY" },
      null,
      2,
    ),
  },
];

export const seedBudgets: Budget[] = [
  {
    agentId: "agt_01",
    dailyCap: 500,
    sessionCap: 150,
    rpm: 20,
    rpd: 2000,
    spentToday: 312.4,
    requestsToday: 842,
  },
  {
    agentId: "agt_02",
    dailyCap: 200,
    sessionCap: 50,
    rpm: 60,
    rpd: 5000,
    spentToday: 61.9,
    requestsToday: 2210,
  },
  {
    agentId: "agt_03",
    dailyCap: 1000,
    sessionCap: 300,
    rpm: 10,
    rpd: 500,
    spentToday: 880,
    requestsToday: 141,
  },
  {
    agentId: "agt_04",
    dailyCap: 50,
    sessionCap: 10,
    rpm: 30,
    rpd: 3000,
    spentToday: 4.2,
    requestsToday: 96,
  },
];

export const seedApprovals: Approval[] = [
  {
    id: "apr_1042",
    agentId: "agt_02",
    toolId: "tl_refund",
    status: "PENDING",
    reason: "Policy 'Refund ceiling': amount 480 > 200",
    payload: { charge_id: "ch_93KD2", amount: 480, currency: "USD", customer: "cus_7712" },
    createdAt: "2026-10-08T15:52:00Z",
  },
  {
    id: "apr_1041",
    agentId: "agt_01",
    toolId: "tl_order",
    status: "PENDING",
    reason: "Risk tier HIGH requires approval",
    payload: { supplier: "Northwind", sku: "SRV-R740", qty: 4, total: 18400 },
    createdAt: "2026-10-08T15:31:00Z",
  },
  {
    id: "apr_1039",
    agentId: "agt_03",
    toolId: "tl_scale",
    status: "APPROVED",
    reason: "Risk tier CRITICAL",
    payload: { service: "checkout", replicas: 12 },
    createdAt: "2026-10-08T11:04:00Z",
    note: "Expected traffic for launch.",
  },
  {
    id: "apr_1035",
    agentId: "agt_02",
    toolId: "tl_refund",
    status: "DENIED",
    reason: "Policy 'Refund ceiling'",
    payload: { charge_id: "ch_11AB", amount: 950 },
    createdAt: "2026-10-07T18:20:00Z",
    note: "Duplicate request.",
  },
  {
    id: "apr_1030",
    agentId: "agt_01",
    toolId: "tl_order",
    status: "EXPIRED",
    reason: "Risk tier HIGH",
    payload: { supplier: "Contoso", qty: 40 },
    createdAt: "2026-10-06T09:12:00Z",
  },
];

// Deterministic demo hash (not cryptographic) for display; verification uses Web Crypto SHA-256.
export async function sha256(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function recordBody(r: Omit<AuditRecord, "hash">) {
  return JSON.stringify([
    r.id,
    r.ts,
    r.agentId,
    r.toolId,
    r.decision,
    r.reason,
    r.payload,
    r.prevHash,
  ]);
}

export const GENESIS = "0".repeat(64);

export const seedAuditRaw: Omit<AuditRecord, "hash" | "prevHash">[] = [
  {
    id: 1,
    ts: "2026-10-08T15:52:00Z",
    agentId: "agt_02",
    toolId: "tl_refund",
    decision: "PENDING",
    reason: "HITL required",
    payload: { amount: 480 },
  },
  {
    id: 2,
    ts: "2026-10-08T15:48:12Z",
    agentId: "agt_02",
    toolId: "tl_mail",
    decision: "ALLOW",
    reason: "All checks passed",
    payload: { to: "customer@acme.test" },
  },
  {
    id: 3,
    ts: "2026-10-08T15:40:03Z",
    agentId: "agt_04",
    toolId: "tl_web",
    decision: "DENY",
    reason: "Agent suspended",
    payload: { url: "https://example.org" },
  },
  {
    id: 4,
    ts: "2026-10-08T15:31:00Z",
    agentId: "agt_01",
    toolId: "tl_order",
    decision: "PENDING",
    reason: "Risk tier HIGH",
    payload: { total: 18400 },
  },
  {
    id: 5,
    ts: "2026-10-08T15:22:47Z",
    agentId: "agt_03",
    toolId: "tl_scale",
    decision: "DENY",
    reason: "Budget: daily cap 88% + projected overrun",
    payload: { replicas: 30 },
  },
  {
    id: 6,
    ts: "2026-10-08T15:10:19Z",
    agentId: "agt_01",
    toolId: "tl_refund",
    decision: "DENY",
    reason: "No permission for tool",
    payload: { amount: 20 },
  },
  {
    id: 7,
    ts: "2026-10-08T14:58:02Z",
    agentId: "agt_02",
    toolId: "tl_refund",
    decision: "ALLOW",
    reason: "Amount within policy",
    payload: { amount: 35 },
  },
];
