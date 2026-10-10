import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, CopyButton, Json, PageHead, Tag } from "@/components/kit";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { pageMeta } from "@/lib/meta";
import { get, post } from "@/lib/api";

export const Route = createFileRoute("/audit")({
  head: () =>
    pageMeta("Audit Vault", "SHA-256 hash-chained, tamper-evident ledger of every decision."),
  component: () => (
    <AppShell>
      <Audit />
    </AppShell>
  ),
});

interface AuditLog {
  id: string;
  organization_id: string;
  agent_id: string | null;
  tool_id: string | null;
  tool_name: string | null;
  event_type: string;
  decision: string;
  payload: Record<string, unknown> | null;
  prev_hash: string;
  current_hash: string;
  sequence_number: number;
  created_at: string;
}

interface AuditListResp {
  total: number;
  items: AuditLog[];
}

interface VerifyResp {
  valid: boolean;
  checked: number;
  broken_at_sequence: number | null;
  message: string;
}

const short = (h: string) => (h ? `${h.slice(0, 8)}…${h.slice(-6)}` : "—");

function Audit() {
  const [rows, setRows] = useState<AuditLog[]>([]);
  const [result, setResult] = useState<VerifyResp | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<AuditLog | null>(null);

  const load = () =>
    get<AuditListResp>("/audit?limit=100")
      .then((r) => setRows(r.items))
      .catch((e: Error) => toast.error(e.message));

  useEffect(() => { load(); }, []);

  const verify = async () => {
    setBusy(true);
    try {
      const r = await post<VerifyResp>("/audit/verify");
      setResult(r);
      if (r.valid) {
        toast.success(`Chain verified — ${r.checked} records checked`);
      } else {
        toast.error(`Chain broken at sequence #${r.broken_at_sequence}`);
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHead
        num="08 · Evidence"
        title="Audit Vault"
        lede="Each record carries the hash of the one before it. Edit one, and the chain shows it."
        action={
          <Button variant="dark" onClick={verify} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Verify SHA-256 chain
          </Button>
        }
      />
      {result && (
        <div
          className={
            result.valid
              ? "mb-6 flex items-center gap-3 bg-teal px-5 py-4 text-teal-foreground"
              : "mb-6 flex items-center gap-3 bg-deny px-5 py-4 text-ivory"
          }
        >
          {result.valid ? <ShieldCheck className="h-5 w-5" /> : <ShieldAlert className="h-5 w-5" />}
          <span className="font-display font-semibold tracking-wide">
            {result.valid
              ? `CHAIN VALID & IMMUTABLE — ${result.checked} records`
              : `CHAIN COMPROMISED — sequence #${result.broken_at_sequence}`}
          </span>
        </div>
      )}
      <div className="overflow-x-auto border border-border bg-ivory">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="eyebrow border-b border-border text-left text-muted-foreground">
            <tr>
              <th className="p-4">#</th>
              <th className="p-4">Time</th>
              <th className="p-4">Event</th>
              <th className="p-4">Decision</th>
              <th className="p-4">Prev hash</th>
              <th className="p-4">Current hash</th>
              <th className="p-4" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr
                key={r.id}
                className={
                  result && !result.valid && result.broken_at_sequence === r.sequence_number
                    ? "bg-deny/10"
                    : "hover:bg-secondary/50"
                }
              >
                <td className="mono p-4">{String(r.sequence_number).padStart(4, "0")}</td>
                <td className="p-4 text-xs">{new Date(r.created_at).toLocaleString()}</td>
                <td className="p-4">
                  <p className="font-display font-semibold">{r.event_type}</p>
                  {r.tool_name && (
                    <p className="mono text-xs text-muted-foreground">→ {r.tool_name}</p>
                  )}
                </td>
                <td className="p-4">
                  <Tag v={r.decision as "ALLOW" | "DENY" | "PENDING"} />
                </td>
                <td className="mono p-4 text-xs text-muted-foreground">{short(r.prev_hash)}</td>
                <td className="mono p-4 text-xs">{short(r.current_hash)}</td>
                <td className="p-4 text-right">
                  <Button variant="ghost" size="sm" onClick={() => setOpen(r)}>
                    Inspect
                  </Button>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-muted-foreground">
                  No audit records yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent className="max-w-xl rounded-none border-border bg-ivory">
          <DialogHeader>
            <DialogTitle className="font-serif-display text-3xl">
              Record #{open?.sequence_number}
            </DialogTitle>
          </DialogHeader>
          {open && (
            <div className="space-y-4 text-sm">
              <dl className="space-y-2">
                <div>
                  <dt className="eyebrow text-muted-foreground">Event type</dt>
                  <dd>{open.event_type}</dd>
                </div>
                <div>
                  <dt className="eyebrow text-muted-foreground">Decision</dt>
                  <dd>{open.decision}</dd>
                </div>
                {open.tool_name && (
                  <div>
                    <dt className="eyebrow text-muted-foreground">Tool</dt>
                    <dd>{open.tool_name}</dd>
                  </div>
                )}
              </dl>
              {open.payload && <Json data={open.payload} />}
              <div>
                <p className="eyebrow text-muted-foreground">Previous hash</p>
                <p className="mono break-all text-xs">{open.prev_hash}</p>
              </div>
              <div>
                <p className="eyebrow text-muted-foreground">Current hash</p>
                <p className="mono break-all text-xs">{open.current_hash}</p>
                <CopyButton value={open.current_hash} label="Copy hash" />
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
