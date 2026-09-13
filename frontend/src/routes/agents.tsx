import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import {
  EmptyState,
  ErrorState,
  HashChip,
  PageHeader,
  Panel,
  StatusBadge,
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
import { Textarea } from "@/components/ui/textarea";
import { api, asList, type Agent, type Budget } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canCreate, canMutate } from "@/lib/rbac";

export const Route = createFileRoute("/agents")({
  head: () => ({
    meta: [
      { title: "Agents — AgentGuard Control Plane" },
      {
        name: "description",
        content:
          "Register, edit and deactivate autonomous agents, with live spend and cap context for each identity.",
      },
      { property: "og:title", content: "Agents — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Register and govern autonomous agent identities.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="agents">
      <AgentsPage />
    </AppShell>
  ),
});

function money(v?: number | null) {
  return v == null ? "Unlimited" : `$${v.toFixed(2)}`;
}

function AgentsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const mayCreate = canCreate(user?.role, "agents");
  const mayMutate = canMutate(user?.role, "agents");

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", description: "" });

  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: async () => asList<Agent>(await api<unknown>("/agents")),
  });
  const budgetsQuery = useQuery({
    queryKey: ["budgets"],
    queryFn: async () => asList<Budget>(await api<unknown>("/budgets")),
  });

  const budgetByAgent = new Map((budgetsQuery.data ?? []).map((b) => [b.agent_id, b]));

  const createMutation = useMutation({
    mutationFn: (body: { name: string; description?: string | undefined }) =>
      api<Agent & { api_key?: string }>("/agents", { method: "POST", body }),
    onSuccess: (data) => {
      toast.success("Agent registered");
      setCreateOpen(false);
      setForm({ name: "", description: "" });
      void qc.invalidateQueries({ queryKey: ["agents"] });
      if (data?.api_key) setApiKey(data.api_key);
      else toast.message("No API key returned by the API for this agent.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api<Agent>(`/agents/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      toast.success("Agent updated");
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api<void>(`/agents/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Agent deactivated");
      void qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <PageHeader
        title="Agents"
        subtitle="Every autonomous identity permitted to dispatch tool calls through AgentGuard."
        actions={
          mayCreate ? (
            <Button onClick={() => setCreateOpen(true)}>+ Register Agent</Button>
          ) : null
        }
      />

      <Panel>
        {agentsQuery.isLoading ? (
          <TableSkeleton rows={6} cols={5} />
        ) : agentsQuery.isError ? (
          <ErrorState message={(agentsQuery.error as Error).message} />
        ) : (agentsQuery.data ?? []).length === 0 ? (
          <EmptyState
            title="No agents registered"
            hint="Register your first agent to issue it a signing key and start enforcing policy."
          />
        ) : (
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                  <th className="px-5 py-3 font-medium">Agent</th>
                  <th className="px-5 py-3 font-medium">ID</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Spend today</th>
                  <th className="px-5 py-3 font-medium">Daily cap</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(agentsQuery.data ?? []).map((agent) => {
                  const budget = budgetByAgent.get(agent.id);
                  return (
                    <tr key={agent.id} className="transition-colors hover:bg-surface-2/50">
                      <td className="px-5 py-3.5">
                        <span className="block text-foreground">{agent.name}</span>
                        {agent.description ? (
                          <span className="block max-w-md truncate text-xs text-muted-foreground">
                            {agent.description}
                          </span>
                        ) : null}
                      </td>
                      <td className="px-5 py-3.5">
                        <HashChip value={agent.id} chars={8} />
                      </td>
                      <td className="px-5 py-3.5">
                        <StatusBadge value={agent.status ?? "ACTIVE"} />
                      </td>
                      <td className="px-5 py-3.5 tabular-nums text-muted-foreground">
                        ${(budget?.current_daily_cost ?? 0).toFixed(2)}
                      </td>
                      <td className="px-5 py-3.5 tabular-nums text-muted-foreground">
                        {money(budget?.max_cost_per_day)}
                      </td>
                      <td className="px-5 py-3.5 text-right whitespace-nowrap">
                        {mayMutate ? (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditing(agent)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-deny hover:text-deny"
                              disabled={
                                deactivateMutation.isPending ||
                                (agent.status ?? "").toUpperCase() === "DELETED"
                              }
                              onClick={() => deactivateMutation.mutate(agent.id)}
                            >
                              Deactivate
                            </Button>
                          </>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Register */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display text-xl">Register agent</DialogTitle>
            <DialogDescription>
              A signing key is issued once at registration and cannot be retrieved later.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="agent-name">Name</Label>
              <Input
                id="agent-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="invoice-reconciler"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-desc">Description</Label>
              <Textarea
                id="agent-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Reconciles supplier invoices against the ledger nightly."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!form.name.trim() || createMutation.isPending}
              onClick={() =>
                createMutation.mutate({
                  name: form.name.trim(),
                  description: form.description.trim() || undefined,
                })
              }
            >
              {createMutation.isPending ? "Registering…" : "Register agent"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* One-time key reveal */}
      <Dialog open={!!apiKey} onOpenChange={(o) => !o && setApiKey(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display text-xl text-brass">
              Copy this API key now
            </DialogTitle>
            <DialogDescription className="text-deny">
              This is the only time the key is shown. It cannot be retrieved again — if it is lost,
              the agent must be re-registered.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md border border-brass/30 bg-brass-soft p-4">
            <p className="font-mono text-xs leading-relaxed break-all text-foreground">{apiKey}</p>
          </div>
          <DialogFooter>
            <Button
              onClick={() => {
                void navigator.clipboard.writeText(apiKey ?? "");
                toast.success("API key copied");
              }}
            >
              Copy key
            </Button>
            <Button variant="ghost" onClick={() => setApiKey(null)}>
              I've stored it
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display text-xl">Edit agent</DialogTitle>
            <DialogDescription>Update the agent's descriptive metadata.</DialogDescription>
          </DialogHeader>
          {editing ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="edit-name">Name</Label>
                <Input
                  id="edit-name"
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-desc">Description</Label>
                <Textarea
                  id="edit-desc"
                  value={editing.description ?? ""}
                  onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button
              disabled={updateMutation.isPending}
              onClick={() =>
                editing &&
                updateMutation.mutate({
                  id: editing.id,
                  body: { name: editing.name, description: editing.description ?? null },
                })
              }
            >
              {updateMutation.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
