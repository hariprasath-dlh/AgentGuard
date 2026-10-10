import { useSyncExternalStore } from "react";
import {
  GENESIS,
  recordBody,
  seedAgents,
  seedApprovals,
  seedAuditRaw,
  seedBudgets,
  seedPermissions,
  seedPolicies,
  seedTools,
  sha256,
  type Agent,
  type Approval,
  type AuditRecord,
  type Budget,
  type Decision,
  type Permission,
  type Policy,
  type Tool,
} from "./demo-data";

export interface DemoState {
  agents: Agent[];
  tools: Tool[];
  permissions: Permission[];
  policies: Policy[];
  budgets: Budget[];
  approvals: Approval[];
  audit: AuditRecord[];
}

const STORAGE = "agentguard_demo_state_v1";
const initial: DemoState = {
  agents: seedAgents,
  tools: seedTools,
  permissions: seedPermissions,
  policies: seedPolicies,
  budgets: seedBudgets,
  approvals: seedApprovals,
  audit: [],
};

let state: DemoState = initial;
let loaded = false;
const listeners = new Set<() => void>();

function emit() {
  if (typeof window !== "undefined") localStorage.setItem(STORAGE, JSON.stringify(state));
  listeners.forEach((l) => l());
}

async function buildAudit() {
  const ordered = [...seedAuditRaw].sort((a, b) => a.id - b.id);
  let prev = GENESIS;
  const out: AuditRecord[] = [];
  for (const r of ordered) {
    const base = { ...r, prevHash: prev };
    const hash = await sha256(recordBody(base));
    out.push({ ...base, hash });
    prev = hash;
  }
  return out;
}

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  const raw = localStorage.getItem(STORAGE);
  if (raw) {
    try {
      state = JSON.parse(raw);
      return;
    } catch {
      /* fall through */
    }
  }
  buildAudit().then((audit) => {
    state = { ...state, audit };
    emit();
  });
}

export function useDemo<T>(sel: (s: DemoState) => T): T {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      load();
      return () => listeners.delete(l);
    },
    () => sel(state),
    () => sel(initial),
  );
}

export function setDemo(fn: (s: DemoState) => DemoState) {
  state = fn(state);
  emit();
}

export function resetDemo() {
  state = initial;
  buildAudit().then((audit) => {
    state = { ...initial, audit };
    emit();
  });
}

export async function appendAudit(
  agentId: string,
  toolId: string,
  decision: Decision,
  reason: string,
  payload: Record<string, unknown>,
) {
  const last = state.audit.reduce((m, r) => (r.id > m.id ? r : m), state.audit[0]);
  const base = {
    id: (last?.id ?? 0) + 1,
    ts: new Date().toISOString(),
    agentId,
    toolId,
    decision,
    reason,
    payload,
    prevHash: last?.hash ?? GENESIS,
  };
  const hash = await sha256(recordBody(base));
  setDemo((s) => ({ ...s, audit: [...s.audit, { ...base, hash }] }));
}

export async function verifyChain(records: AuditRecord[]) {
  const ordered = [...records].sort((a, b) => a.id - b.id);
  let prev = GENESIS;
  for (const r of ordered) {
    if (r.prevHash !== prev) return { valid: false, brokenAt: r.id };
    const h = await sha256(recordBody(r));
    if (h !== r.hash) return { valid: false, brokenAt: r.id };
    prev = r.hash;
  }
  return { valid: true as const, brokenAt: null };
}

export const nameOf = {
  agent: (s: DemoState, id: string) => s.agents.find((a) => a.id === id)?.name ?? id,
  tool: (s: DemoState, id: string) => s.tools.find((t) => t.id === id)?.name ?? id,
};
