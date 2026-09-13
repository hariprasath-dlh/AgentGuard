import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import {
  EmptyState,
  ErrorState,
  PageHeader,
  Panel,
  TableSkeleton,
} from "@/components/app/primitives";
import { AppShell } from "@/components/app/shell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, asList, type Policy } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canMutate } from "@/lib/rbac";

export const Route = createFileRoute("/policies")({
  head: () => ({
    meta: [
      { title: "Policies — AgentGuard Control Plane" },
      {
        name: "description",
        content:
          "Author the allow/block rules, risk thresholds and per-call cost ceilings enforced before an agent dispatches a tool.",
      },
      { property: "og:title", content: "Policies — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Author the rules enforced before an agent dispatches a tool call.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="policies">
      <PoliciesPage />
    </AppShell>
  ),
});

const POLICY_TYPES = ["ALLOWLIST", "BLOCKLIST", "RISK", "COST"];
const RISKS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

type RuleForm = {
  name: string;
  description: string;
  policy_type: string;
  allowed_actions: string;
  blocked_actions: string;
  risk_threshold: string;
  max_cost_per_call: string;
};

const emptyForm: RuleForm = {
  name: "",
  description: "",
  policy_type: "ALLOWLIST",
  allowed_actions: "",
  blocked_actions: "",
  risk_threshold: "",
  max_cost_per_call: "",
};

function buildRules(form: RuleForm): Record<string, unknown> {
  const rules: Record<string, unknown> = {};
  const allowed = form.allowed_actions
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const blocked = form.blocked_actions
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (allowed.length) rules["allowed_actions"] = allowed;
  if (blocked.length) rules["blocked_actions"] = blocked;
  if (form.risk_threshold) rules["risk_thresholds"] = { max_risk_level: form.risk_threshold };
  if (form.max_cost_per_call.trim() !== "")
    rules["max_cost_per_call"] = Number(form.max_cost_per_call);
  return rules;
}

function summarize(rules?: Record<string, unknown> | null) {
  if (!rules || Object.keys(rules).length === 0) return "No rules";
  const parts: string[] = [];
  const allowed = rules["allowed_actions"];
  const blocked = rules["blocked_actions"];
  const risk = rules["risk_thresholds"] as { max_risk_level?: string } | undefined;
  const cost = rules["max_cost_per_call"];
  if (Array.isArray(allowed)) parts.push(`${allowed.length} allowed`);
  if (Array.isArray(blocked)) parts.push(`${blocked.length} blocked`);
  if (risk?.max_risk_level) parts.push(`max risk ${risk.max_risk_level}`);
  if (typeof cost === "number") parts.push(`≤ $${cost} / call`);
  return parts.join(" · ") || "Custom rules";
}

function PoliciesPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const mayMutate = canMutate(user?.role, "policies");

  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<RuleForm>(emptyForm);

  const policiesQuery = useQuery({
    queryKey: ["policies"],
    queryFn: async () => asList<Policy>(await api<unknown>("/policies")),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const rules = buildRules(form);
      const body = {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        policy_type: form.policy_type,
        rules,
      };
      return editingId
        ? api<Policy>(`/policies/${editingId}`, { method: "PATCH", body })
        : api<Policy>("/policies", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(editingId ? "Policy updated" : "Policy created");
      setOpen(false);
      setEditingId(null);
      setForm(emptyForm);
      void qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api<Policy>(`/policies/${id}`, { method: "PATCH", body: { is_active: active } }),
    onSuccess: () => {
      toast.success("Policy updated");
      void qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api<void>(`/policies/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Policy removed");
      void qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function openEdit(policy: Policy) {
    const rules = policy.rules ?? {};
    const allowed = rules["allowed_actions"];
    const blocked = rules["blocked_actions"];
    const risk = rules["risk_thresholds"] as { max_risk_level?: string } | undefined;
    const cost = rules["max_cost_per_call"];
    setForm({
      name: policy.name,
      description: policy.description ?? "",
      policy_type: (policy.policy_type ?? "ALLOWLIST").toUpperCase(),
      allowed_actions: Array.isArray(allowed) ? allowed.join(", ") : "",
      blocked_actions: Array.isArray(blocked) ? blocked.join(", ") : "",
      risk_threshold: risk?.max_risk_level ?? "",
      max_cost_per_call: typeof cost === "number" ? String(cost) : "",
    });
    setEditingId(policy.id);
    setOpen(true);
  }

  const rulesValid = Object.keys(buildRules(form)).length > 0;

  return (
    <>
      <PageHeader
        title="Policies"
        subtitle="Deterministic rules evaluated before dispatch — allowed and blocked actions, risk ceilings and per-call cost limits."
        actions={
          mayMutate ? (
            <Button
              onClick={() => {
                setForm(emptyForm);
                setEditingId(null);
                setOpen(true);
              }}
            >
              + New Policy
            </Button>
          ) : null
        }
      />

      <Panel>
        {policiesQuery.isLoading ? (
          <TableSkeleton rows={5} cols={4} />
        ) : policiesQuery.isError ? (
          <ErrorState message={(policiesQuery.error as Error).message} />
        ) : (policiesQuery.data ?? []).length === 0 ? (
          <EmptyState
            title="No policies defined"
            hint="Without a policy, dispatch decisions fall back to permissions and budgets alone."
          />
        ) : (
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                  <th className="px-5 py-3 font-medium">Policy</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">Rules</th>
                  <th className="px-5 py-3 font-medium">Active</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(policiesQuery.data ?? []).map((policy) => (
                  <tr key={policy.id} className="transition-colors hover:bg-surface-2/50">
                    <td className="px-5 py-3.5">
                      <span className="block text-foreground">{policy.name}</span>
                      {policy.description ? (
                        <span className="block max-w-md truncate text-xs text-muted-foreground">
                          {policy.description}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-5 py-3.5 text-muted-foreground">
                      {policy.policy_type ?? "—"}
                    </td>
                    <td className="px-5 py-3.5 text-muted-foreground">
                      {summarize(policy.rules)}
                    </td>
                    <td className="px-5 py-3.5">
                      <Switch
                        checked={policy.is_active !== false}
                        disabled={!mayMutate || toggleMutation.isPending}
                        onCheckedChange={(checked) =>
                          toggleMutation.mutate({ id: policy.id, active: checked })
                        }
                      />
                    </td>
                    <td className="px-5 py-3.5 text-right whitespace-nowrap">
                      {mayMutate ? (
                        <>
                          <Button variant="ghost" size="sm" onClick={() => openEdit(policy)}>
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-deny hover:text-deny"
                            disabled={deleteMutation.isPending}
                            onClick={() => deleteMutation.mutate(policy.id)}
                          >
                            Remove
                          </Button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display text-xl">
              {editingId ? "Edit policy" : "New policy"}
            </DialogTitle>
            <DialogDescription>
              At least one rule is required. Actions are comma separated.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="p-name">Name</Label>
              <Input
                id="p-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Treasury guardrails"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-desc">Description</Label>
              <Textarea
                id="p-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Restricts payment tooling to read-only actions under $50 per call."
              />
            </div>
            <div className="space-y-2">
              <Label>Policy type</Label>
              <Select
                value={form.policy_type}
                onValueChange={(v) => setForm({ ...form, policy_type: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {POLICY_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-allow">Allowed actions</Label>
              <Input
                id="p-allow"
                value={form.allowed_actions}
                onChange={(e) => setForm({ ...form, allowed_actions: e.target.value })}
                placeholder="read_ledger, list_invoices"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-block">Blocked actions</Label>
              <Input
                id="p-block"
                value={form.blocked_actions}
                onChange={(e) => setForm({ ...form, blocked_actions: e.target.value })}
                placeholder="send_wire_transfer"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Max risk level</Label>
                <Select
                  value={form.risk_threshold || "NONE"}
                  onValueChange={(v) => setForm({ ...form, risk_threshold: v === "NONE" ? "" : v })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Not set" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="NONE">Not set</SelectItem>
                    {RISKS.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="p-cost">Max cost per call ($)</Label>
                <Input
                  id="p-cost"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.max_cost_per_call}
                  onChange={(e) => setForm({ ...form, max_cost_per_call: e.target.value })}
                  placeholder="50.00"
                />
              </div>
            </div>
            {!rulesValid ? (
              <p className="text-xs text-pending">
                Add at least one rule — allowed actions, blocked actions, a risk ceiling or a
                per-call cost limit.
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!form.name.trim() || !rulesValid || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              {saveMutation.isPending ? "Saving…" : editingId ? "Save changes" : "Create policy"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
