import type { Role } from "./api";

export type Screen =
  | "dashboard"
  | "agents"
  | "tools"
  | "policies"
  | "budgets"
  | "approvals"
  | "audit"
  | "settings";

export type Access = "none" | "read" | "write";

type Matrix = Record<Role, Record<Screen, Access>>;

/** Mirrors backend enforcement — the UI never grants more than the API allows. */
export const ACCESS: Matrix = {
  ADMIN: {
    dashboard: "write",
    agents: "write",
    tools: "write",
    policies: "write",
    budgets: "write",
    approvals: "write",
    audit: "write",
    settings: "read",
  },
  SECURITY: {
    dashboard: "read",
    agents: "write",
    tools: "write",
    policies: "write",
    budgets: "write",
    approvals: "none",
    audit: "none",
    settings: "read",
  },
  AUDITOR: {
    dashboard: "read",
    agents: "read",
    tools: "read",
    policies: "read",
    budgets: "read",
    approvals: "none",
    audit: "write",
    settings: "read",
  },
  MANAGER: {
    dashboard: "read",
    agents: "read",
    tools: "read",
    policies: "read",
    budgets: "read",
    approvals: "write",
    audit: "none",
    settings: "read",
  },
  DEVELOPER: {
    dashboard: "none",
    agents: "write",
    tools: "write",
    policies: "none",
    budgets: "none",
    approvals: "none",
    audit: "none",
    settings: "read",
  },
};

export function accessFor(role: Role | undefined, screen: Screen): Access {
  if (!role) return "none";
  return ACCESS[role]?.[screen] ?? "none";
}

export function canRead(role: Role | undefined, screen: Screen) {
  return accessFor(role, screen) !== "none";
}

/** DEVELOPER may create agents/tools but not edit or deactivate them. */
export function canCreate(role: Role | undefined, screen: Screen) {
  return accessFor(role, screen) === "write";
}

export function canMutate(role: Role | undefined, screen: Screen) {
  if (role === "DEVELOPER" && (screen === "agents" || screen === "tools")) return false;
  return accessFor(role, screen) === "write";
}

/** First screen a role can actually land on. */
export function landingRoute(role: Role | undefined): string {
  const order: Array<[Screen, string]> = [
    ["dashboard", "/dashboard"],
    ["approvals", "/approvals"],
    ["agents", "/agents"],
    ["audit", "/audit"],
    ["settings", "/settings"],
  ];
  for (const [screen, path] of order) if (canRead(role, screen)) return path;
  return "/settings";
}
