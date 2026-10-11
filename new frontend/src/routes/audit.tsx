import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Json, PageHead, Tag } from "@/components/kit";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { pageMeta } from "@/lib/meta";
import { get, post } from "@/lib/api";
import {
  parseAuditVerification,
  type AuditVerificationBackendResponse,
  type ParsedVerification,
} from "@/lib/audit-verifier";

export const Route = createFileRoute("/audit")({
  head: () =>
    pageMeta(
      "Audit Vault",
      "Tamper-evident, cryptographically chained audit log of every decision.",
    ),
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

const short = (h: string) => (h ? `${h.slice(0, 8)}…${h.slice(-6)}` : "—");

function Audit() {
  const [rows, setRows] = useState<AuditLog[]>([]);
  const [result, setResult] = useState<ParsedVerification | null>(null);
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
      const raw = await post<AuditVerificationBackendResponse>("/audit/verify");
      const r = parseAuditVerification(raw);
      setResult(r);
      if (r.isValid) {
        toast.success(`Chain verified — ${r.totalRecords} records checked: ${r.message}`);
      } else {
        toast.error(`Chain broken at sequence #${r.brokenSequenceNumber}: ${r.message}`);
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
            result.isValid
              ? "mb-6 flex flex-col gap-1 bg-teal px-5 py-4 text-teal-foreground"
              : "mb-6 flex flex-col gap-1 bg-deny px-5 py-4 text-ivory"
          }
        >
          <div className="flex items-center gap-3">
            {result.isValid ? <ShieldCheck className="h-5 w-5" /> : <ShieldAlert className="h-5 w-5" />}
            <span className="font-display font-semibold tracking-wide">
              {result.isValid
                ? `CHAIN VALID & IMMUTABLE — ${result.totalRecords} records scanned`
                : `CHAIN COMPROMISED — sequence #${result.brokenSequenceNumber}`}
            </span>
          </div>
          <p className="pl-8 text-xs opacity-90">{result.message}</p>
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
                  result && !result.isValid && result.brokenSequenceNumber === r.sequence_number
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
                <td className="mono p-4 text-xs text-muted-foreground">
                  {short(r.prev_hash)}
                </td>
                <td className="mono p-4 text-xs">{short(r.current_hash)}</td>
                <td className="p-4 text-right">
                  <Button variant="ghost" size="sm" onClick={() => setOpen(r)}>
                    View
                  </Button>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-muted-foreground">
                  No audit log entries recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={Boolean(open)} onOpenChange={(o) => !o && setOpen(null)}>
        {open && (
          <DialogContent className="max-w-xl rounded-none border-border bg-ivory">
            <DialogHeader>
              <DialogTitle className="font-serif-display text-2xl">
                Audit record #{String(open.sequence_number).padStart(4, "0")} · {open.event_type}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 border border-border bg-card p-4 text-xs">
                <div>
                  <p className="eyebrow text-muted-foreground">Timestamp</p>
                  <p className="mt-1">{new Date(open.created_at).toISOString()}</p>
                </div>
                <div>
                  <p className="eyebrow text-muted-foreground">Decision</p>
                  <p className="mt-1">
                    <Tag v={open.decision as "ALLOW" | "DENY" | "PENDING"} />
                  </p>
                </div>
                <div>
                  <p className="eyebrow text-muted-foreground">Previous SHA-256</p>
                  <p className="mono mt-1 break-all">{open.prev_hash || "GENESIS (None)"}</p>
                </div>
                <div>
                  <p className="eyebrow text-muted-foreground">Current SHA-256</p>
                  <p className="mono mt-1 break-all">{open.current_hash}</p>
                </div>
              </div>
              <div>
                <p className="eyebrow mb-2 text-muted-foreground">Payload data</p>
                <Json data={open.payload} />
              </div>
            </div>
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
