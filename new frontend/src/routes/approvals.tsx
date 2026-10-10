import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Confirm, Empty, Json, PageHead, Tag, textareaCls } from "@/components/kit";
import { pageMeta } from "@/lib/meta";
import { cn } from "@/lib/utils";
import { get, post } from "@/lib/api";

export const Route = createFileRoute("/approvals")({
  head: () => pageMeta("Approvals", "Human-in-the-loop review queue for high-risk agent actions."),
  component: () => (
    <AppShell>
      <Approvals />
    </AppShell>
  ),
});

interface HITLItem {
  id: string;
  organization_id: string;
  tool_request_id: string;
  status: string;
  reviewer_id: string | null;
  review_notes: string | null;
  expires_at: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  tool_name: string | null;
  agent_id: string | null;
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
}

interface HITLListResp {
  total: number;
  items: HITLItem[];
}

const tabs = ["PENDING", "APPROVED", "DENIED", "EXPIRED"] as const;

function Approvals() {
  const [items, setItems] = useState<HITLItem[]>([]);
  const [tab, setTab] = useState<(typeof tabs)[number]>("PENDING");
  const [sel, setSel] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [actioning, setActioning] = useState(false);

  const load = async () => {
    try {
      const resp = await get<HITLListResp>("/hitl");
      setItems(resp.items);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const list = items.filter((i) => i.status === tab);
  const shown = list.find((i) => i.id === sel) ?? list[0] ?? null;

  const decide = async (id: string, action: "approve" | "deny") => {
    setActioning(true);
    try {
      await post(`/hitl/${id}/${action}`, { review_notes: note || null });
      toast.success(action === "approve" ? "Approved — tool executed" : "Action denied");
      setNote("");
      setSel(null);
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setActioning(false);
    }
  };

  const countFor = (t: string) => items.filter((i) => i.status === t).length;

  return (
    <>
      <PageHead
        num="07 · Human in the loop"
        title="Approvals"
        lede="High-risk requests wait here until a reviewer decides."
      />
      <div className="mb-6 flex flex-wrap border-b border-border">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setSel(null);
            }}
            className={cn(
              "eyebrow -mb-px border-b-2 px-4 py-3 transition-colors",
              tab === t
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t} <span className="ml-1 opacity-60">{countFor(t)}</span>
          </button>
        ))}
      </div>
      {!list.length ? (
        <Empty>Nothing {tab.toLowerCase()} right now.</Empty>
      ) : (
        <div className="grid gap-6 lg:grid-cols-12">
          <ul className="space-y-2 lg:col-span-4">
            {list.map((a) => (
              <li key={a.id}>
                <button
                  onClick={() => setSel(a.id)}
                  className={cn(
                    "w-full border p-4 text-left transition-colors",
                    shown?.id === a.id
                      ? "border-foreground bg-ivory"
                      : "border-border hover:bg-ivory",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="mono text-xs">{a.id.slice(0, 8)}…</span>
                    <Tag v={a.status as "PENDING" | "APPROVED" | "DENIED"} />
                  </div>
                  <p className="mt-2 font-display font-semibold">{a.tool_name ?? "Unknown tool"}</p>
                  <p className="mono text-xs text-muted-foreground">
                    Agent: {a.agent_id?.slice(0, 8) ?? "—"}
                  </p>
                </button>
              </li>
            ))}
          </ul>
          {shown && (
            <div className="border border-border bg-ivory lg:col-span-8">
              <div className="flex items-center justify-between border-b border-border px-6 py-4">
                <span className="eyebrow">Request {shown.id.slice(0, 8)}…</span>
                <Tag v={shown.status as "PENDING" | "APPROVED" | "DENIED"} />
              </div>
              <div className="grid gap-6 p-6 md:grid-cols-2">
                <dl className="space-y-4 text-sm">
                  <div>
                    <dt className="eyebrow text-muted-foreground">Tool</dt>
                    <dd className="mt-1 font-display font-semibold">{shown.tool_name ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="eyebrow text-muted-foreground">Agent ID</dt>
                    <dd className="mono mt-1 text-xs">{shown.agent_id ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="eyebrow text-muted-foreground">Requested</dt>
                    <dd className="mt-1">{new Date(shown.created_at).toLocaleString()}</dd>
                  </div>
                  {shown.expires_at && (
                    <div>
                      <dt className="eyebrow text-muted-foreground">Expires</dt>
                      <dd className="mt-1">{new Date(shown.expires_at).toLocaleString()}</dd>
                    </div>
                  )}
                  {shown.review_notes && (
                    <div>
                      <dt className="eyebrow text-muted-foreground">Reviewer note</dt>
                      <dd className="mt-1 italic">{shown.review_notes}</dd>
                    </div>
                  )}
                </dl>
                {shown.input_payload && (
                  <div>
                    <p className="eyebrow mb-2 text-muted-foreground">Payload</p>
                    <Json data={shown.input_payload} />
                  </div>
                )}
              </div>
              {shown.status === "PENDING" && (
                <div className="space-y-4 border-t border-border p-6">
                  <label htmlFor="note" className="eyebrow text-muted-foreground">
                    Reviewer notes
                  </label>
                  <textarea
                    id="note"
                    rows={3}
                    className={textareaCls}
                    placeholder="Why are you approving or denying?"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                  <div className="flex flex-wrap gap-3">
                    <Confirm
                      title="Approve & execute?"
                      description="The tool will be called with this exact payload."
                      confirmLabel="Approve & Execute"
                      onConfirm={() => decide(shown.id, "approve")}
                      trigger={
                        <Button variant="allow" disabled={actioning}>
                          Approve &amp; Execute
                        </Button>
                      }
                    />
                    <Confirm
                      title="Deny this action?"
                      description="The tool will not be called. The agent receives a DENY."
                      confirmLabel="Deny Action"
                      onConfirm={() => decide(shown.id, "deny")}
                      trigger={
                        <Button variant="outline" disabled={actioning}>
                          Deny Action
                        </Button>
                      }
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
