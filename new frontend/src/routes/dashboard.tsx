import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { PageHead, Panel, Tag } from "@/components/kit";
import { pageMeta } from "@/lib/meta";
import { cn } from "@/lib/utils";
import { get } from "@/lib/api";

export const Route = createFileRoute("/dashboard")({
  head: () =>
    pageMeta("Dashboard", "Live overview of agent requests, decisions, spend and approvals."),
  component: () => (
    <AppShell>
      <Dashboard />
    </AppShell>
  ),
});

interface BudgetUtil {
  agent_id: string;
  agent_name: string;
  current_spend: number;
  max_budget_per_day: number | null;
}

interface Stats {
  total_agents: number;
  total_tools: number;
  requests_today: number;
  allowed_today: number;
  blocked_today: number;
  pending_today: number;
  total_spend_today: number;
  budget_utilization: BudgetUtil[];
}

interface ActivityItem {
  request_id: string;
  agent_id: string;
  agent_name: string;
  tool_name: string;
  decision: string;
  reason: string;
  latency_ms: number | null;
  created_at: string;
}

interface ActivityFeed {
  total: number;
  items: ActivityItem[];
}

function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [error, setError] = useState("");

  const load = () => {
    get<Stats>("/dashboard/stats")
      .then(setStats)
      .catch((e: Error) => setError(e.message));
    get<ActivityFeed>("/dashboard/activity?limit=8")
      .then((f) => setActivity(f.items))
      .catch(() => {});
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  if (error) {
    return (
      <>
        <PageHead num="01 · Overview" title="Dashboard" lede="Live overview of your organization." />
        <p className="text-sm text-deny">{error}</p>
      </>
    );
  }

  const s = stats;
  const spend = s?.total_spend_today ?? 0;
  const totalCap = (s?.budget_utilization ?? []).reduce(
    (a, b) => a + (b.max_budget_per_day ?? 0),
    0,
  );

  const statCards = s
    ? [
        ["Requests today", s.requests_today.toLocaleString()],
        ["Allowed", s.allowed_today.toLocaleString(), "text-allow"],
        ["Blocked", s.blocked_today.toLocaleString(), "text-deny"],
        ["Pending", s.pending_today.toLocaleString(), "text-pending"],
        ["Spend today", `$${Number(spend).toFixed(2)}`],
        ["Active agents", String(s.total_agents)],
        ["Registered tools", String(s.total_tools)],
        ["Pending approvals", s.pending_today.toLocaleString(), "text-pending"],
      ]
    : [];

  return (
    <>
      <PageHead
        num="01 · Overview"
        title="Dashboard"
        lede="What your agents attempted today, and what AgentGuard decided."
      />
      {s ? (
        <>
          <div className="grid grid-cols-2 border-l border-t border-border md:grid-cols-4">
            {statCards.map(([l, v, c]) => (
              <div key={l} className="border-b border-r border-border bg-ivory p-5">
                <p className="eyebrow text-muted-foreground">{l}</p>
                <p className={cn("mt-3 font-serif-display text-4xl md:text-5xl", c)}>{v}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 grid gap-8 xl:grid-cols-12">
            <Panel
              title="Live activity"
              num="A"
              className="xl:col-span-8"
              action={
                <Link to="/audit" className="eyebrow text-primary">
                  Audit vault →
                </Link>
              }
            >
              <ul className="divide-y divide-border">
                {activity.map((r) => (
                  <li
                    key={r.request_id}
                    className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3 text-sm"
                  >
                    <Tag v={r.decision as "ALLOW" | "DENY" | "PENDING"} />
                    <span className="font-display font-semibold">{r.agent_name}</span>
                    <span className="mono text-xs text-muted-foreground">→ {r.tool_name}</span>
                    <span className="w-full text-muted-foreground sm:ml-auto sm:w-auto">
                      {r.reason}
                    </span>
                  </li>
                ))}
                {!activity.length && (
                  <li className="py-6 text-muted-foreground">No activity yet today.</li>
                )}
              </ul>
            </Panel>
            <Panel title="Budget utilization" num="B" className="xl:col-span-4">
              {totalCap > 0 ? (
                <>
                  <p className="font-serif-display text-5xl">
                    {Math.round((spend / totalCap) * 100)}%
                  </p>
                  <p className="text-sm text-muted-foreground">
                    ${Number(spend).toFixed(0)} of ${totalCap} daily cap across agents
                  </p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No budget caps configured.</p>
              )}
              <div className="mt-6 space-y-4">
                {(s?.budget_utilization ?? []).map((b) => {
                  const cap = b.max_budget_per_day ?? 0;
                  const pct = cap > 0 ? Math.min(100, (b.current_spend / cap) * 100) : 0;
                  return (
                    <div key={b.agent_id}>
                      <div className="flex justify-between text-xs">
                        <span>{b.agent_name}</span>
                        <span className="mono">
                          {cap > 0 ? `${pct.toFixed(0)}%` : "No cap"}
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 bg-secondary">
                        <div
                          className={cn(
                            "h-full transition-all duration-700",
                            pct > 85 ? "bg-deny" : pct > 60 ? "bg-pending" : "bg-teal",
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
              <Link
                to="/approvals"
                className="mt-8 flex items-center justify-between bg-brown-dark px-4 py-3 text-brown-foreground hover:bg-brown"
              >
                <span className="text-sm">{s?.pending_today ?? 0} approvals waiting</span>{" "}
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </Panel>
          </div>
        </>
      ) : (
        <div className="py-16 text-center text-muted-foreground">Loading dashboard…</div>
      )}
    </>
  );
}
