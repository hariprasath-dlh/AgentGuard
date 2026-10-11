import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Field, Input, PageHead } from "@/components/kit";
import { pageMeta } from "@/lib/meta";
import { cn } from "@/lib/utils";
import { get, patch } from "@/lib/api";

export const Route = createFileRoute("/budgets")({
  head: () => pageMeta("Budgets", "Daily and session spend caps plus rate limits per agent."),
  component: () => (
    <AppShell>
      <Budgets />
    </AppShell>
  ),
});

interface Budget {
  id: string;
  agent_id: string;
  agent_name?: string;
  current_spend: number;
  max_budget_per_day: number | null;
  max_budget_per_session: number | null;
  max_requests_per_minute: number | null;
  max_requests_per_day: number | null;
}

function BudgetCard({ b, agentName, onSaved }: { b: Budget; agentName: string; onSaved: () => void }) {
  const [f, setF] = useState({
    max_budget_per_day: b.max_budget_per_day ?? "",
    max_budget_per_session: b.max_budget_per_session ?? "",
    max_requests_per_minute: b.max_requests_per_minute ?? "",
    max_requests_per_day: b.max_requests_per_day ?? "",
  });
  const [loading, setLoading] = useState(false);

  const cap = b.max_budget_per_day ?? 0;
  const pct = cap > 0 ? Math.min(100, (b.current_spend / cap) * 100) : 0;

  return (
    <article className="border border-border bg-ivory p-6">
      <div className="flex items-baseline justify-between">
        <h3 className="font-serif-display text-3xl">{agentName}</h3>
        {cap > 0 && (
          <span
            className={cn(
              "font-serif-display text-4xl",
              pct > 85 ? "text-deny" : pct > 60 ? "text-pending" : "text-foreground",
            )}
          >
            {pct.toFixed(0)}%
          </span>
        )}
      </div>
      <p className="text-sm text-muted-foreground">
        ${Number(b.current_spend).toFixed(2)} spent today
        {cap > 0 ? ` of $${cap} cap` : " (no cap)"}
      </p>
      {cap > 0 && (
        <div className="mt-3">
          <div className="h-1.5 bg-secondary">
            <div
              className={cn("h-full", pct > 85 ? "bg-deny" : pct > 60 ? "bg-pending" : "bg-teal")}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}
      <form
        className="mt-6 grid grid-cols-2 gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setLoading(true);
          const body: Record<string, number | null> = {};
          body["max_budget_per_day"] = f.max_budget_per_day !== "" ? Number(f.max_budget_per_day) : null;
          body["max_budget_per_session"] = f.max_budget_per_session !== "" ? Number(f.max_budget_per_session) : null;
          body["max_requests_per_minute"] = f.max_requests_per_minute !== "" ? Number(f.max_requests_per_minute) : null;
          body["max_requests_per_day"] = f.max_requests_per_day !== "" ? Number(f.max_requests_per_day) : null;
          try {
            await patch(`/budgets/${b.id}`, body);
            toast.success(`Limits updated for ${agentName}`);
            onSaved();
          } catch (err) {
            toast.error((err as Error).message);
          } finally {
            setLoading(false);
          }
        }}
      >
        {(
          [
            ["max_budget_per_day", "Daily cap (USD)"],
            ["max_budget_per_session", "Session cap (USD)"],
            ["max_requests_per_minute", "Requests / minute"],
            ["max_requests_per_day", "Requests / day"],
          ] as [keyof typeof f, string][]
        ).map(([k, label]) => (
          <Field key={k} label={label} htmlFor={b.id + k}>
            <Input
              id={b.id + k}
              type="number"
              min={0}
              placeholder="unlimited"
              value={String(f[k])}
              onChange={(e) => setF({ ...f, [k]: e.target.value })}
            />
          </Field>
        ))}
        <Button type="submit" variant="dark" className="col-span-2" disabled={loading}>
          Save limits
        </Button>
      </form>
    </article>
  );
}

function Budgets() {
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [agentNames, setAgentNames] = useState<Record<string, string>>({});

  const load = async () => {
    try {
      const [bs, agents] = await Promise.all([
        get<Budget[]>("/budgets"),
        get<{ id: string; name: string }[]>("/agents"),
      ]);
      setBudgets(bs);
      const names: Record<string, string> = {};
      agents.forEach((a) => (names[a.id] = a.name));
      setAgentNames(names);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <>
      <PageHead
        num="06 · Spend control"
        title="Budgets"
        lede="Caps that stop runaway loops before they reach your invoice."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        {budgets.map((b) => (
          <BudgetCard
            key={b.id}
            b={b}
            agentName={agentNames[b.agent_id] ?? b.agent_id}
            onSaved={load}
          />
        ))}
        {!budgets.length && (
          <p className="col-span-2 py-12 text-center text-muted-foreground">
            No budgets found. Create an agent to provision one automatically.
          </p>
        )}
      </div>
    </>
  );
}
