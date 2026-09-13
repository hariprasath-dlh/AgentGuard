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
import { api, asList, type Agent, type Budget } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canMutate } from "@/lib/rbac";

export const Route = createFileRoute("/budgets")({
  head: () => ({
    meta: [
      { title: "Budgets — AgentGuard Control Plane" },
      {
        name: "description",
        content:
          "Request-rate and spend ceilings per agent, with live session and daily consumption against each cap.",
      },
      { property: "og:title", content: "Budgets — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Rate and spend ceilings per agent with live consumption.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="budgets">
      <BudgetsPage />
    </AppShell>
  ),
});

type CapForm = {
  max_requests_per_minute: string;
  max_requests_per_day: string;
  max_cost_per_session: string;
  max_cost_per_day: string;
};

function toForm(b: Budget): CapForm {
  const s = (v?: number | null) => (v == null ? "" : String(v));
  return {
    max_requests_per_minute: s(b.max_requests_per_minute),
    max_requests_per_day: s(b.max_requests_per_day),
    max_cost_per_session: s(b.max_cost_per_session),
    max_cost_per_day: s(b.max_cost_per_day),
  };
}

/** Empty input means "clear back to unlimited" → send null, not 0. */
function toBody(form: CapForm): Record<string, number | null> {
  const n = (v: string) => (v.trim() === "" ? null : Number(v));
  return {
    max_requests_per_minute: n(form.max_requests_per_minute),
    max_requests_per_day: n(form.max_requests_per_day),
    max_cost_per_session: n(form.max_cost_per_session),
    max_cost_per_day: n(form.max_cost_per_day),
  };
}

const cap = (v?: number | null, prefix = "") =>
  v == null ? "Unlimited" : `${prefix}${prefix ? v.toFixed(2) : v}`;

function BudgetsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const mayMutate = canMutate(user?.role, "budgets");

  const [editing, setEditing] = useState<Budget | null>(null);
  const [form, setForm] = useState<CapForm | null>(null);

  const budgetsQuery = useQuery({
    queryKey: ["budgets"],
    queryFn: async () => asList<Budget>(await api<unknown>("/budgets")),
  });
  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: async () => asList<Agent>(await api<unknown>("/agents")),
  });

  const agentName = (id: string) => agentsQuery.data?.find((a) => a.id === id)?.name ?? id;

  const saveMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, number | null> }) =>
      api<Budget>(`/budgets/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      toast.success("Caps updated");
      setEditing(null);
      setForm(null);
      void qc.invalidateQueries({ queryKey: ["budgets"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <PageHeader
        title="Budgets"
        subtitle="Rate and spend ceilings evaluated on every dispatch. Cleared fields mean unlimited."
      />

      <Panel>
        {budgetsQuery.isLoading ? (
          <TableSkeleton rows={5} cols={6} />
        ) : budgetsQuery.isError ? (
          <ErrorState message={(budgetsQuery.error as Error).message} />
        ) : (budgetsQuery.data ?? []).length === 0 ? (
          <EmptyState
            title="No budgets configured"
            hint="Budgets are created alongside agents; configure caps once an agent exists."
          />
        ) : (
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                  <th className="px-5 py-3 font-medium">Agent</th>
                  <th className="px-5 py-3 font-medium">Req / min</th>
                  <th className="px-5 py-3 font-medium">Req / day</th>
                  <th className="px-5 py-3 font-medium">Session cap</th>
                  <th className="px-5 py-3 font-medium">Daily cap</th>
                  <th className="px-5 py-3 font-medium">Spend today</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(budgetsQuery.data ?? []).map((b) => (
                  <tr key={b.id} className="transition-colors hover:bg-surface-2/50">
                    <td className="px-5 py-3.5 text-foreground">{agentName(b.agent_id)}</td>
                    <td className="px-5 py-3.5 tabular-nums text-muted-foreground">
                      {cap(b.max_requests_per_minute)}
                    </td>
                    <td className="px-5 py-3.5 tabular-nums text-muted-foreground">
                      {cap(b.max_requests_per_day)}
                    </td>
                    <td className="px-5 py-3.5 tabular-nums text-muted-foreground">
                      {cap(b.max_cost_per_session, "$")}
                    </td>
                    <td className="px-5 py-3.5 tabular-nums text-muted-foreground">
                      {cap(b.max_cost_per_day, "$")}
                    </td>
                    <td className="px-5 py-3.5 tabular-nums text-foreground">
                      ${(b.current_daily_cost ?? 0).toFixed(2)}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {mayMutate ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditing(b);
                            setForm(toForm(b));
                          }}
                        >
                          Configure caps
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Dialog
        open={!!editing}
        onOpenChange={(o) => {
          if (!o) {
            setEditing(null);
            setForm(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display text-xl">Configure caps</DialogTitle>
            <DialogDescription>
              {editing ? agentName(editing.agent_id) : ""} — leave a field empty for unlimited.
            </DialogDescription>
          </DialogHeader>
          {form ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="rpm">Requests per minute</Label>
                <Input
                  id="rpm"
                  type="number"
                  min="0"
                  value={form.max_requests_per_minute}
                  onChange={(e) =>
                    setForm({ ...form, max_requests_per_minute: e.target.value })
                  }
                  placeholder="Unlimited"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rpd">Requests per day</Label>
                <Input
                  id="rpd"
                  type="number"
                  min="0"
                  value={form.max_requests_per_day}
                  onChange={(e) => setForm({ ...form, max_requests_per_day: e.target.value })}
                  placeholder="Unlimited"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cps">Cost per session ($)</Label>
                <Input
                  id="cps"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.max_cost_per_session}
                  onChange={(e) => setForm({ ...form, max_cost_per_session: e.target.value })}
                  placeholder="Unlimited"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cpd">Cost per day ($)</Label>
                <Input
                  id="cpd"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.max_cost_per_day}
                  onChange={(e) => setForm({ ...form, max_cost_per_day: e.target.value })}
                  placeholder="Unlimited"
                />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setEditing(null);
                setForm(null);
              }}
            >
              Cancel
            </Button>
            <Button
              disabled={saveMutation.isPending}
              onClick={() =>
                editing && form && saveMutation.mutate({ id: editing.id, body: toBody(form) })
              }
            >
              {saveMutation.isPending ? "Saving…" : "Save caps"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
