import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import {
  CountUp,
  EmptyState,
  ErrorState,
  FadeIn,
  PageHeader,
  Panel,
  StatusBadge,
  TableSkeleton,
  JsonBlock,
} from "@/components/app/primitives";
import { AppShell } from "@/components/app/shell";
import { api, asList, type ActivityItem, type DashboardStats } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — AgentGuard Control Plane" },
      {
        name: "description",
        content:
          "Live agent governance overview: request volume, allow/deny/pending decisions, spend and budget utilization.",
      },
      { property: "og:title", content: "Dashboard — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Live agent decision volume, spend and budget utilization.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="dashboard">
      <DashboardPage />
    </AppShell>
  ),
});

function StatTile({
  label,
  value,
  decimals = 0,
  prefix = "",
  tone,
}: {
  label: string;
  value: number;
  decimals?: number;
  prefix?: string;
  tone?: "allow" | "deny" | "pending" | "brass";
}) {
  const toneClass =
    tone === "allow"
      ? "text-allow"
      : tone === "deny"
        ? "text-deny"
        : tone === "pending"
          ? "text-pending"
          : tone === "brass"
            ? "text-brass"
            : "text-foreground";
  return (
    <div className="panel px-5 py-5">
      <p className="text-[11px] tracking-[0.14em] text-muted-foreground uppercase">{label}</p>
      <p className={cn("mt-3 font-display text-3xl tracking-tight tabular-nums", toneClass)}>
        <CountUp value={value} decimals={decimals} prefix={prefix} />
      </p>
    </div>
  );
}

const FILTERS = ["ALL", "ALLOW", "DENY", "PENDING"] as const;

function DashboardPage() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("ALL");
  const [open, setOpen] = useState<string | null>(null);

  const statsQuery = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api<DashboardStats>("/dashboard/stats"),
    refetchInterval: 15000,
  });

  const activityQuery = useQuery({
    queryKey: ["dashboard-activity"],
    queryFn: async () =>
      asList<ActivityItem>(await api<unknown>("/dashboard/activity?limit=25&offset=0")),
    // Poll every 5s; TanStack pauses polling when the tab/window isn't focused.
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const stats = statsQuery.data;
  const utilization = stats?.budget_utilization ?? [];

  const rows = useMemo(() => {
    const items = activityQuery.data ?? [];
    if (filter === "ALL") return items;
    return items.filter((i) => (i.decision ?? "").toUpperCase().startsWith(filter));
  }, [activityQuery.data, filter]);

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Pre-dispatch decisions across every registered agent, refreshed continuously."
      />

      {statsQuery.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="panel h-[104px] p-5">
              <div className="shimmer h-3 w-24 rounded" />
              <div className="shimmer mt-5 h-7 w-16 rounded" />
            </div>
          ))}
        </div>
      ) : statsQuery.isError ? (
        <Panel>
          <ErrorState message={(statsQuery.error as Error).message} />
        </Panel>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile label="Total agents" value={stats?.total_agents ?? 0} />
          <StatTile label="Total tools" value={stats?.total_tools ?? 0} />
          <StatTile label="Requests today" value={stats?.requests_today ?? 0} />
          <StatTile
            label="Spend today"
            value={stats?.total_spend_today ?? 0}
            decimals={2}
            prefix="$"
            tone="brass"
          />
          <StatTile label="Allowed today" value={stats?.allowed_today ?? 0} tone="allow" />
          <StatTile label="Blocked today" value={stats?.blocked_today ?? 0} tone="deny" />
          <StatTile label="Pending today" value={stats?.pending_today ?? 0} tone="pending" />
          <StatTile
            label="Agents over 80% budget"
            value={utilization.filter((u) => (u.utilization_percent ?? 0) >= 80).length}
            tone="pending"
          />
        </div>
      )}

      <FadeIn delay={0.05} className="mt-6">
        <Panel title="Budget utilization">
          {utilization.length === 0 ? (
            <EmptyState
              title="No budget data yet"
              hint="Utilization appears once agents have daily caps configured and spend recorded."
            />
          ) : (
            <div className="space-y-5 px-5 py-5">
              {utilization.map((u) => {
                const pct = Math.min(100, Math.round(u.utilization_percent ?? 0));
                const bar =
                  pct >= 90 ? "bg-deny" : pct >= 70 ? "bg-risk-high" : "bg-teal";
                return (
                  <div key={u.agent_id}>
                    <div className="flex items-baseline justify-between gap-4 text-sm">
                      <span className="truncate text-foreground">
                        {u.agent_name || u.agent_id}
                      </span>
                      <span className="tabular-nums text-muted-foreground">
                        ${(u.daily_cost ?? 0).toFixed(2)} /{" "}
                        {u.daily_limit == null ? "Unlimited" : `$${u.daily_limit.toFixed(2)}`}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                      <motion.div
                        className={cn("h-full rounded-full", bar)}
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ type: "spring", stiffness: 90, damping: 22 }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Panel>
      </FadeIn>

      <FadeIn delay={0.1} className="mt-6">
        <Panel
          title="Live activity"
          actions={
            <div className="flex gap-1.5">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-[11px] tracking-[0.1em] uppercase transition-colors",
                    filter === f
                      ? "border-brass/40 bg-brass-soft text-brass"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          }
        >
          {activityQuery.isLoading ? (
            <TableSkeleton rows={6} cols={5} />
          ) : activityQuery.isError ? (
            <ErrorState message={(activityQuery.error as Error).message} />
          ) : rows.length === 0 ? (
            <EmptyState
              title="No activity in this view"
              hint="Decisions stream in here as agents dispatch tool calls."
            />
          ) : (
            <ul className="divide-y divide-border">
              <AnimatePresence initial={false}>
                {rows.map((row) => {
                  const ts = row.timestamp || row.created_at;
                  const expanded = open === row.id;
                  return (
                    <motion.li
                      key={row.id}
                      layout
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ type: "spring", stiffness: 140, damping: 22 }}
                    >
                      <button
                        type="button"
                        onClick={() => setOpen(expanded ? null : row.id)}
                        className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-4 px-5 py-3.5 text-left transition-colors hover:bg-surface-2/60 sm:grid-cols-[130px_1fr_auto_auto_auto]"
                      >
                        <span className="font-mono text-xs text-muted-foreground">
                          {ts ? new Date(ts).toLocaleTimeString() : "—"}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm text-foreground">
                            {row.agent_name || row.agent_id || "Unknown agent"} →{" "}
                            {row.tool_name || "unknown tool"}
                          </span>
                          {row.reason ? (
                            <span className="block truncate text-xs text-muted-foreground">
                              {row.reason}
                            </span>
                          ) : null}
                        </span>
                        <StatusBadge value={row.decision} />
                        <span className="hidden text-xs tabular-nums text-muted-foreground sm:block">
                          {row.latency_ms != null ? `${row.latency_ms} ms` : "—"}
                        </span>
                        <ChevronDown
                          className={cn(
                            "size-4 text-muted-foreground transition-transform",
                            expanded && "rotate-180",
                          )}
                        />
                      </button>
                      <AnimatePresence>
                        {expanded ? (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden px-5 pb-4"
                          >
                            <JsonBlock data={row.payload ?? row} />
                          </motion.div>
                        ) : null}
                      </AnimatePresence>
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
          )}
        </Panel>
      </FadeIn>
    </>
  );
}
