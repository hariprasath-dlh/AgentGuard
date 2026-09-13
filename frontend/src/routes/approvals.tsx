import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  EmptyState,
  ErrorState,
  JsonBlock,
  PageHeader,
  Panel,
  RiskBadge,
  StatusBadge,
  TableSkeleton,
} from "@/components/app/primitives";
import { AppShell } from "@/components/app/shell";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, asList, type Agent, type HitlRequest } from "@/lib/api";

export const Route = createFileRoute("/approvals")({
  head: () => ({
    meta: [
      { title: "Approvals — AgentGuard Control Plane" },
      {
        name: "description",
        content:
          "Human-in-the-loop queue for high-risk agent actions held before dispatch, with full parameter review.",
      },
      { property: "og:title", content: "Approvals — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Review and decide high-risk agent actions held before dispatch.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="approvals">
      <ApprovalsPage />
    </AppShell>
  ),
});

function Countdown({ expiresAt }: { expiresAt?: string | null | undefined }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!expiresAt) return <span className="text-xs text-muted-foreground">No expiry</span>;
  const diff = new Date(expiresAt).getTime() - now;
  if (diff <= 0) return <span className="text-xs text-deny">Expired</span>;
  const mins = Math.floor(diff / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  return (
    <span className="font-mono text-xs text-pending tabular-nums">
      expires in {mins}m {String(secs).padStart(2, "0")}s
    </span>
  );
}

function ApprovalsPage() {
  const qc = useQueryClient();
  const [notes, setNotes] = useState<Record<string, string>>({});

  const pendingQuery = useQuery({
    queryKey: ["hitl", "PENDING"],
    queryFn: async () => asList<HitlRequest>(await api<unknown>("/hitl?status=PENDING")),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });
  const historyQuery = useQuery({
    queryKey: ["hitl", "history"],
    queryFn: async () => asList<HitlRequest>(await api<unknown>("/hitl")),
  });
  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: async () => asList<Agent>(await api<unknown>("/agents")),
  });

  const agentName = (id: string) => agentsQuery.data?.find((a) => a.id === id)?.name ?? id;

  // Irreversible: never optimistic — the card waits for the server response.
  const decide = useMutation({
    mutationFn: ({
      id,
      action,
      review_notes,
    }: {
      id: string;
      action: "approve" | "deny";
      review_notes?: string | undefined;
    }) =>
      api<HitlRequest>(`/hitl/${id}/${action}`, {
        method: "POST",
        body: review_notes ? { review_notes } : {},
      }),
    onSuccess: (_data, vars) => {
      toast.success(vars.action === "approve" ? "Request approved" : "Request denied");
      void qc.invalidateQueries({ queryKey: ["hitl"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const history = (historyQuery.data ?? []).filter((r) =>
    ["APPROVED", "DENIED", "EXPIRED"].includes((r.status ?? "").toUpperCase()),
  );

  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="High-risk actions paused before dispatch, awaiting a human decision."
      />

      <Tabs defaultValue="pending">
        <TabsList>
          <TabsTrigger value="pending">
            Pending{pendingQuery.data?.length ? ` (${pendingQuery.data.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="mt-5">
          {pendingQuery.isLoading ? (
            <Panel>
              <TableSkeleton rows={3} cols={3} />
            </Panel>
          ) : pendingQuery.isError ? (
            <Panel>
              <ErrorState message={(pendingQuery.error as Error).message} />
            </Panel>
          ) : (pendingQuery.data ?? []).length === 0 ? (
            <Panel>
              <EmptyState
                title="Nothing awaiting review"
                hint="High-risk dispatches appear here the moment policy holds them."
              />
            </Panel>
          ) : (
            <div className="grid gap-4">
              <AnimatePresence initial={false}>
                {(pendingQuery.data ?? []).map((req) => {
                  const busy = decide.isPending && decide.variables?.id === req.id;
                  return (
                    <motion.div
                      key={req.id}
                      layout
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.98 }}
                      transition={{ type: "spring", stiffness: 130, damping: 20 }}
                      className="panel px-5 py-5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-display text-lg tracking-tight">
                            {req.tool_name || req.tool_id || "Unknown tool"}
                          </p>
                          <p className="mt-0.5 text-sm text-muted-foreground">
                            requested by {agentName(req.agent_id)}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <RiskBadge level={req.risk_level} />
                          <Countdown expiresAt={req.expires_at} />
                        </div>
                      </div>

                      {req.reason ? (
                        <p className="mt-4 text-sm text-foreground">{req.reason}</p>
                      ) : null}

                      <div className="mt-4">
                        <p className="mb-2 text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                          Requested parameters
                        </p>
                        <JsonBlock data={req.parameters ?? {}} />
                      </div>

                      <Textarea
                        className="mt-4"
                        placeholder="Review notes (optional)"
                        value={notes[req.id] ?? ""}
                        onChange={(e) => setNotes({ ...notes, [req.id]: e.target.value })}
                      />

                      <div className="mt-4 flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          className="text-deny hover:text-deny"
                          disabled={decide.isPending}
                          onClick={() =>
                            decide.mutate({
                              id: req.id,
                              action: "deny",
                              review_notes: notes[req.id]?.trim() || undefined,
                            })
                          }
                        >
                          {busy ? "Submitting…" : "Deny"}
                        </Button>
                        <Button
                          disabled={decide.isPending}
                          onClick={() =>
                            decide.mutate({
                              id: req.id,
                              action: "approve",
                              review_notes: notes[req.id]?.trim() || undefined,
                            })
                          }
                        >
                          {busy ? "Submitting…" : "Approve"}
                        </Button>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-5">
          <Panel>
            {historyQuery.isLoading ? (
              <TableSkeleton rows={5} cols={4} />
            ) : historyQuery.isError ? (
              <ErrorState message={(historyQuery.error as Error).message} />
            ) : history.length === 0 ? (
              <EmptyState title="No decided requests yet" />
            ) : (
              <div className="w-full overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                      <th className="px-5 py-3 font-medium">Decided</th>
                      <th className="px-5 py-3 font-medium">Tool</th>
                      <th className="px-5 py-3 font-medium">Agent</th>
                      <th className="px-5 py-3 font-medium">Outcome</th>
                      <th className="px-5 py-3 font-medium">Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {history.map((req) => (
                      <tr key={req.id} className="transition-colors hover:bg-surface-2/50">
                        <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">
                          {req.reviewed_at
                            ? new Date(req.reviewed_at).toLocaleString()
                            : req.requested_at
                              ? new Date(req.requested_at).toLocaleString()
                              : "—"}
                        </td>
                        <td className="px-5 py-3.5 text-foreground">
                          {req.tool_name || req.tool_id || "—"}
                        </td>
                        <td className="px-5 py-3.5 text-muted-foreground">
                          {agentName(req.agent_id)}
                        </td>
                        <td className="px-5 py-3.5">
                          <StatusBadge value={req.status} />
                        </td>
                        <td className="max-w-xs truncate px-5 py-3.5 text-muted-foreground">
                          {req.review_notes || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </TabsContent>
      </Tabs>
    </>
  );
}
