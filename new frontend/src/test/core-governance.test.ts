import { beforeEach, describe, expect, it } from "vitest";
import { appendAudit, resetDemo, setDemo, verifyChain, type DemoState } from "@/lib/store";
import {
  GENESIS,
  recordBody,
  seedAgents,
  seedApprovals,
  seedBudgets,
  seedPermissions,
  seedPolicies,
  seedTools,
  sha256,
  type Agent,
  type Approval,
  type AuditRecord,
  type Tool,
} from "@/lib/demo-data";

describe("Core Governance Engine Workflows", () => {
  beforeEach(() => {
    localStorage.clear();
    resetDemo();
  });

  describe("Agent Lifecycle & Kill Switch", () => {
    it("creates a new agent with valid schema and API key format", () => {
      const newAgent: Agent = {
        id: "agt_test_001",
        name: "Order Processing Agent",
        description: "Handles e-commerce fulfillment orders",
        status: "ACTIVE",
        apiKey: "ag_demo_a1b2c3d4e5f60718",
        keyRevealed: false,
        createdAt: "2026-10-09",
      };

      setDemo((s) => ({ ...s, agents: [...s.agents, newAgent] }));

      let currentAgents: Agent[] = [];
      setDemo((s) => {
        currentAgents = s.agents;
        return s;
      });

      const found = currentAgents.find((a) => a.id === "agt_test_001");
      expect(found).toBeDefined();
      expect(found?.name).toBe("Order Processing Agent");
      expect(found?.apiKey.startsWith("ag_demo_")).toBe(true);
      expect(found?.status).toBe("ACTIVE");
    });

    it("toggles agent status as emergency kill switch", () => {
      const agentId = seedAgents[0].id;

      // Suspend / kill switch
      setDemo((s) => ({
        ...s,
        agents: s.agents.map((a) => (a.id === agentId ? { ...a, status: "SUSPENDED" } : a)),
      }));

      let currentAgents: Agent[] = [];
      setDemo((s) => {
        currentAgents = s.agents;
        return s;
      });
      expect(currentAgents.find((a) => a.id === agentId)?.status).toBe("SUSPENDED");

      // Reactivate
      setDemo((s) => ({
        ...s,
        agents: s.agents.map((a) => (a.id === agentId ? { ...a, status: "ACTIVE" } : a)),
      }));

      setDemo((s) => {
        currentAgents = s.agents;
        return s;
      });
      expect(currentAgents.find((a) => a.id === agentId)?.status).toBe("ACTIVE");
    });
  });

  describe("Tool Registry & Risk Classification", () => {
    it("registers new tools with risk tiers and endpoint mappings", () => {
      const tool: Tool = {
        id: "tl_stripe_charge",
        name: "payments.charge",
        endpoint: "POST /v1/charges",
        risk: "HIGH",
        active: true,
        description: "Creates charges on customer cards",
      };

      setDemo((s) => ({ ...s, tools: [...s.tools, tool] }));

      let currentTools: Tool[] = [];
      setDemo((s) => {
        currentTools = s.tools;
        return s;
      });

      const found = currentTools.find((t) => t.id === "tl_stripe_charge");
      expect(found).toBeDefined();
      expect(found?.risk).toBe("HIGH");
      expect(found?.active).toBe(true);
    });

    it("supports retiring and reactivating tools", () => {
      const toolId = seedTools[0].id;

      setDemo((s) => ({
        ...s,
        tools: s.tools.map((t) => (t.id === toolId ? { ...t, active: false } : t)),
      }));

      let currentTools: Tool[] = [];
      setDemo((s) => {
        currentTools = s.tools;
        return s;
      });
      expect(currentTools.find((t) => t.id === toolId)?.active).toBe(false);
    });
  });

  describe("Permissions Matrix (Default Deny)", () => {
    it("grants and revokes agent-tool access explicitly", () => {
      const agentId = "agt_finance";
      const toolId = "tl_payments_refund";

      // Initially not present
      let permissionsState: DemoState["permissions"] = [];
      setDemo((s) => {
        permissionsState = s.permissions;
        return s;
      });

      const hasInitial = permissionsState.some((p) => p.agentId === agentId && p.toolId === toolId);
      expect(hasInitial).toBe(false);

      // Grant permission
      setDemo((s) => ({
        ...s,
        permissions: [...s.permissions, { agentId, toolId }],
      }));

      setDemo((s) => {
        permissionsState = s.permissions;
        return s;
      });
      expect(permissionsState.some((p) => p.agentId === agentId && p.toolId === toolId)).toBe(true);

      // Revoke permission
      setDemo((s) => ({
        ...s,
        permissions: s.permissions.filter((p) => !(p.agentId === agentId && p.toolId === toolId)),
      }));

      setDemo((s) => {
        permissionsState = s.permissions;
        return s;
      });
      expect(permissionsState.some((p) => p.agentId === agentId && p.toolId === toolId)).toBe(
        false,
      );
    });
  });

  describe("Policies & JSON Rule Validation", () => {
    it("validates valid JSON configurations for policies", () => {
      const validConfig = JSON.stringify({
        rule: "amount <= 500",
        action: "ALLOW",
      });

      expect(() => JSON.parse(validConfig)).not.toThrow();
    });

    it("rejects malformed JSON configurations", () => {
      const badConfig = "{ amount: 500, action: 'ALLOW' "; // syntax error
      expect(() => JSON.parse(badConfig)).toThrow();
    });
  });

  describe("Human-in-the-Loop (HITL) Approvals", () => {
    it("approves pending request and appends ALLOW audit record", async () => {
      const pendingItem = seedApprovals.find((a) => a.status === "PENDING");
      expect(pendingItem).toBeDefined();

      if (!pendingItem) return;

      const reviewerNote = "Verified customer claim against transaction receipt";

      setDemo((s) => ({
        ...s,
        approvals: s.approvals.map((x) =>
          x.id === pendingItem.id ? { ...x, status: "APPROVED", note: reviewerNote } : x,
        ),
      }));

      await appendAudit(
        pendingItem.agentId,
        pendingItem.toolId,
        "ALLOW",
        `Approved by reviewer: ${reviewerNote}`,
        pendingItem.payload,
      );

      let currentState: DemoState = {
        agents: [],
        tools: [],
        permissions: [],
        policies: [],
        budgets: [],
        approvals: [],
        audit: [],
      };
      setDemo((s) => {
        currentState = s;
        return s;
      });

      const updatedApproval = currentState.approvals.find((a) => a.id === pendingItem.id);
      expect(updatedApproval?.status).toBe("APPROVED");
      expect(updatedApproval?.note).toBe(reviewerNote);

      const latestAudit = currentState.audit[currentState.audit.length - 1];
      expect(latestAudit.decision).toBe("ALLOW");
      expect(latestAudit.agentId).toBe(pendingItem.agentId);
      expect(latestAudit.reason).toContain("Approved by reviewer");
    });

    it("denies pending request and appends DENY audit record", async () => {
      const pendingItem = seedApprovals.find((a) => a.status === "PENDING");
      expect(pendingItem).toBeDefined();

      if (!pendingItem) return;

      setDemo((s) => ({
        ...s,
        approvals: s.approvals.map((x) =>
          x.id === pendingItem.id ? { ...x, status: "DENIED", note: "Excessive refund amount" } : x,
        ),
      }));

      await appendAudit(
        pendingItem.agentId,
        pendingItem.toolId,
        "DENY",
        "Denied by reviewer: Excessive refund amount",
        pendingItem.payload,
      );

      let currentState: DemoState = {
        agents: [],
        tools: [],
        permissions: [],
        policies: [],
        budgets: [],
        approvals: [],
        audit: [],
      };
      setDemo((s) => {
        currentState = s;
        return s;
      });

      const updated = currentState.approvals.find((a) => a.id === pendingItem.id);
      expect(updated?.status).toBe("DENIED");

      const latestAudit = currentState.audit[currentState.audit.length - 1];
      expect(latestAudit.decision).toBe("DENY");
    });
  });

  describe("Audit Vault & Cryptographic Chain Integrity", () => {
    it("validates a sound, unaltered hash chain", async () => {
      const record1: AuditRecord = {
        id: 1,
        ts: "2026-10-09T08:00:00Z",
        agentId: "agt_support",
        toolId: "crm.lookup",
        decision: "ALLOW",
        reason: "Access allowed by policy",
        payload: { user_id: "usr_1" },
        prevHash: GENESIS,
        hash: "",
      };
      record1.hash = await sha256(recordBody(record1));

      const record2: AuditRecord = {
        id: 2,
        ts: "2026-10-09T08:01:00Z",
        agentId: "agt_support",
        toolId: "payments.refund",
        decision: "DENY",
        reason: "Refund ceiling exceeded",
        payload: { amount: 800 },
        prevHash: record1.hash,
        hash: "",
      };
      record2.hash = await sha256(recordBody(record2));

      const chain = [record1, record2];
      const result = await verifyChain(chain);

      expect(result.valid).toBe(true);
      expect(result.brokenAt).toBeNull();
    });

    it("detects tampering when an audit entry payload or reason is altered", async () => {
      const record1: AuditRecord = {
        id: 1,
        ts: "2026-10-09T08:00:00Z",
        agentId: "agt_support",
        toolId: "crm.lookup",
        decision: "ALLOW",
        reason: "Legitimate request",
        payload: { user_id: "usr_1" },
        prevHash: GENESIS,
        hash: "",
      };
      record1.hash = await sha256(recordBody(record1));

      const record2: AuditRecord = {
        id: 2,
        ts: "2026-10-09T08:01:00Z",
        agentId: "agt_support",
        toolId: "payments.refund",
        decision: "DENY",
        reason: "Blocked by security rule",
        payload: { amount: 500 },
        prevHash: record1.hash,
        hash: "",
      };
      record2.hash = await sha256(recordBody(record2));

      // Attacker tampers with record 1's reason without knowing secret or updating downstream hashes
      const tamperedRecord1 = {
        ...record1,
        reason: "Falsified reason",
      };

      const result = await verifyChain([tamperedRecord1, record2]);
      expect(result.valid).toBe(false);
      expect(result.brokenAt).toBe(1);
    });

    it("detects broken link when previous hash does not match", async () => {
      const record1: AuditRecord = {
        id: 1,
        ts: "2026-10-09T08:00:00Z",
        agentId: "agt_support",
        toolId: "crm.lookup",
        decision: "ALLOW",
        reason: "Legitimate request",
        payload: { user_id: "usr_1" },
        prevHash: GENESIS,
        hash: "",
      };
      record1.hash = await sha256(recordBody(record1));

      const record2: AuditRecord = {
        id: 2,
        ts: "2026-10-09T08:01:00Z",
        agentId: "agt_support",
        toolId: "payments.refund",
        decision: "DENY",
        reason: "Blocked by security rule",
        payload: { amount: 500 },
        prevHash: "0000000000000000000000000000000000000000000000000000000000000000", // Mismatched!
        hash: "",
      };
      record2.hash = await sha256(recordBody(record2));

      const result = await verifyChain([record1, record2]);
      expect(result.valid).toBe(false);
      expect(result.brokenAt).toBe(2);
    });
  });
});
