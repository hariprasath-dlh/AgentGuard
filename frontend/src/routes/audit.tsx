import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { Fragment, useState } from "react";
import { toast } from "sonner";

import {
  EmptyState,
  ErrorState,
  HashChip,
  JsonBlock,
  PageHeader,
  Panel,
  StatusBadge,
  TableSkeleton,
} from "@/components/app/primitives";
import { AppShell } from "@/components/app/shell";
import { Button } from "@/components/ui/button";
import { api, asList, type AuditLog, type ChainVerification } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "Audit Vault — AgentGuard Control Plane" },
      {
        name: "description",
        content:
          "Hash-chained, tamper-evident record of every governance decision, with one-click chain verification.",
      },
      { property: "og:title", content: "Audit Vault — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Tamper-evident, hash-chained record of every governance decision.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="audit">
      <AuditPage />
    </AppShell>
  ),
});

function ChainVisual({
  logs,
  result,
  sweeping,
}: {
  logs: AuditLog[];
  result: ChainVerification | null;
  sweeping: boolean;
}) {
  const reduce = useReducedMotion();
  const links = logs.slice(0, 12);
  const brokenAt = result && result.status !== "VALID" ? (result.broken_sequence_number ?? null) : null;

  return (
    <div className="relative px-6 py-8">
      <div className="relative flex flex-col gap-3">
        {/* Sweep beam */}
        {sweeping && !reduce ? (
          <motion.div
            className="pointer-events-none absolute inset-x-0 h-16 rounded-full bg-brass/12 blur-md"
            initial={{ top: 0, opacity: 0 }}
            animate={{ top: ["0%", "100%"], opacity: [0, 1, 0] }}
            transition={{ duration: 1.6, ease: "easeInOut" }}
          />
        ) : null}

        {links.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            The chain is empty — records appear as agents are governed.
          </p>
        ) : (
          links.map((log, i) => {
            const broken = brokenAt != null && log.sequence_number === brokenAt;
            const beforeBreak = brokenAt == null || log.sequence_number < brokenAt;
            const verified = !!result && result.status === "VALID";
            const tone = broken
              ? "border-deny/60 bg-deny/12 text-deny"
              : verified || (result && beforeBreak)
                ? "border-allow/45 bg-allow/10 text-allow"
                : "border-border bg-surface-2 text-muted-foreground";
            return (
              <div key={log.id} className="relative">
                {i > 0 ? (
                  <span
                    className={cn(
                      "absolute -top-3 left-5 h-3 w-px",
                      broken ? "bg-deny" : verified ? "bg-allow" : "bg-border",
                      broken && "opacity-40",
                    )}
                  />
                ) : null}
                <motion.div
                  initial={false}
                  animate={
                    broken && !reduce
                      ? { x: [0, -6, 6, -3, 0] }
                      : { x: 0 }
                  }
                  transition={{ duration: 0.5 }}
                  className={cn(
                    "flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors",
                    tone,
                  )}
                >
                  <span className="font-mono text-[11px] tabular-nums opacity-80">
                    #{log.sequence_number}
                  </span>
                  <span className="mono-chip">{(log.current_hash ?? "").slice(0, 16)}…</span>
                  <span className="text-xs">
                    {broken ? "chain broken at this record" : (log.event_type ?? "record")}
                  </span>
                </motion.div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function AuditPage() {
  const [open, setOpen] = useState<string | null>(null);
  const [sweeping, setSweeping] = useState(false);
  const [result, setResult] = useState<ChainVerification | null>(null);

  const logsQuery = useQuery({
    queryKey: ["audit"],
    queryFn: async () => asList<AuditLog>(await api<unknown>("/audit?limit=50&offset=0")),
  });

  const verify = useMutation({
    mutationFn: () => api<ChainVerification>("/audit/verify", { method: "POST" }),
    onMutate: () => {
      setResult(null);
      setSweeping(true);
    },
    onSuccess: (data) => {
      // Let the sweep play out before settling the chain into its final state.
      setTimeout(() => {
        setSweeping(false);
        setResult(data);
        if (data.status === "VALID") toast.success("Chain verified — no tampering detected");
        else toast.error("Chain integrity check failed");
      }, 1400);
    },
    onError: (e: Error) => {
      setSweeping(false);
      toast.error(e.message);
    },
  });

  const logs = logsQuery.data ?? [];

  return (
    <>
      <PageHeader
        title="Audit Vault"
        subtitle="Every decision is hash-chained to the one before it. Verify the chain to prove nothing was altered."
        actions={
          <Button onClick={() => verify.mutate()} disabled={verify.isPending || sweeping}>
            {verify.isPending || sweeping ? "Verifying…" : "Verify Chain"}
          </Button>
        }
      />

      <Panel title="Chain integrity">
        <AnimatePresence mode="wait">
          {result ? (
            (() => {
              const isChainValid = result.status === "VALID";
              return (
                <motion.div
                  key={isChainValid ? "valid" : "invalid"}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "mx-6 mt-6 rounded-lg border px-5 py-4",
                    isChainValid
                      ? "border-allow/40 bg-allow/8"
                      : "border-deny/45 bg-deny/10",
                  )}
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <StatusBadge value={isChainValid ? "VALID" : "INVALID"} />
                    <span className="text-sm text-foreground">
                      {isChainValid
                        ? `${result.records_verified ?? result.total_records ?? logs.length} records verified`
                        : `Chain breaks at record #${result.broken_sequence_number ?? "unknown"}`}
                    </span>
                    {result.verified_at ? (
                      <span className="font-mono text-xs text-muted-foreground">
                        {new Date(result.verified_at).toLocaleString()}
                      </span>
                    ) : null}
                  </div>
                  {!isChainValid && (result.error || result.details) ? (
                    <p className="mt-2 text-sm text-deny">{result.error || result.details}</p>
                  ) : null}
                </motion.div>
              );
            })()
          ) : null}
        </AnimatePresence>

        {logsQuery.isLoading ? (
          <TableSkeleton rows={5} cols={2} />
        ) : (
          <ChainVisual logs={logs} result={result} sweeping={sweeping} />
        )}
      </Panel>

      <Panel title="Audit log" className="mt-6">
        {logsQuery.isLoading ? (
          <TableSkeleton rows={6} cols={5} />
        ) : logsQuery.isError ? (
          <ErrorState message={(logsQuery.error as Error).message} />
        ) : logs.length === 0 ? (
          <EmptyState
            title="No audit records yet"
            hint="Each governance decision is appended here and sealed into the hash chain."
          />
        ) : (
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                  <th className="px-5 py-3 font-medium">Seq</th>
                  <th className="px-5 py-3 font-medium">Timestamp</th>
                  <th className="px-5 py-3 font-medium">Event</th>
                  <th className="px-5 py-3 font-medium">Decision</th>
                  <th className="px-5 py-3 font-medium">Hash</th>
                  <th className="px-5 py-3 font-medium">Prev hash</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {logs.map((log) => {
                  const expanded = open === log.id;
                  const ts = log.timestamp || log.created_at;
                  return (
                    <Fragment key={log.id}>
                      <tr
                        className="cursor-pointer transition-colors hover:bg-surface-2/50"
                        onClick={() => setOpen(expanded ? null : log.id)}
                      >
                        <td className="px-5 py-3.5 font-mono text-xs tabular-nums text-muted-foreground">
                          #{log.sequence_number}
                        </td>
                        <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">
                          {ts ? new Date(ts).toLocaleString() : "—"}
                        </td>
                        <td className="px-5 py-3.5 text-foreground">{log.event_type ?? "—"}</td>
                        <td className="px-5 py-3.5">
                          {log.decision ? <StatusBadge value={log.decision} /> : "—"}
                        </td>
                        <td className="px-5 py-3.5" onClick={(e) => e.stopPropagation()}>
                          <HashChip value={log.current_hash} chars={12} />
                        </td>
                        <td className="px-5 py-3.5" onClick={(e) => e.stopPropagation()}>
                          <HashChip value={log.previous_hash} chars={12} />
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <ChevronDown
                            className={cn(
                              "inline size-4 text-muted-foreground transition-transform",
                              expanded && "rotate-180",
                            )}
                          />
                        </td>
                      </tr>
                      {expanded ? (
                        <tr>
                          <td colSpan={7} className="px-5 pb-4">
                            <JsonBlock data={log.event_data ?? log} />
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
