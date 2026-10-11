import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Confirm, Empty, Field, Input, PageHead, Tag, textareaCls } from "@/components/kit";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { pageMeta } from "@/lib/meta";
import { get, post, patch, del } from "@/lib/api";

export const Route = createFileRoute("/policies")({
  head: () => pageMeta("Policies", "Governance rules evaluated on every agent tool request."),
  component: () => (
    <AppShell>
      <Policies />
    </AppShell>
  ),
});

type PolicyType = "RISK" | "PARAM_DENYLIST";

interface Policy {
  id: string;
  name: string;
  description: string;
  policy_type: PolicyType;
  rules: Record<string, unknown>;
  is_active: boolean;
}

const TEMPLATES: Record<PolicyType, string> = {
  RISK: JSON.stringify(
    {
      LOW: "ALLOW",
      MEDIUM: "ALLOW",
      HIGH: "HITL",
      CRITICAL: "DENY",
    },
    null,
    2,
  ),
  PARAM_DENYLIST: JSON.stringify(
    {
      patterns: [
        "(?i)\\bdrop\\s+table\\b",
        "(?i)\\bdelete\\s+from\\b",
        "(?i)\\btruncate\\s+table\\b",
        "(?i)\\brm\\s+-rf\\b",
      ],
    },
    null,
    2,
  ),
};

function Policies() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [edit, setEdit] = useState<Partial<Policy> & { rulesText?: string } | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const load = () =>
    get<Policy[]>("/policies")
      .then(setPolicies)
      .catch((e: Error) => toast.error(e.message));

  useEffect(() => { load(); }, []);

  const openNew = (type: PolicyType = "RISK") => {
    setErr("");
    setEdit({
      name: type === "RISK" ? "Risk Level Governance" : "Prohibited Parameters Denylist",
      description:
        type === "RISK"
          ? "Enforces deterministic ALLOW, HITL or DENY actions per risk level."
          : "Blocks destructive SQL injection and shell commands in payloads.",
      policy_type: type,
      rulesText: TEMPLATES[type],
    });
  };

  const save = async () => {
    setErr("");
    if (!edit?.name?.trim()) return setErr("Name is required.");
    const policyType: PolicyType = edit.policy_type === "PARAM_DENYLIST" ? "PARAM_DENYLIST" : "RISK";

    let rules: Record<string, unknown>;
    try {
      rules = JSON.parse(edit.rulesText ?? "{}");
      if (typeof rules !== "object" || rules === null || Array.isArray(rules)) {
        return setErr("Rules must be a valid JSON object.");
      }
    } catch {
      return setErr("Rules must be valid JSON syntax.");
    }

    setLoading(true);
    try {
      if (edit.id) {
        await patch(`/policies/${edit.id}`, {
          name: edit.name,
          description: edit.description,
          rules,
        });
        toast.success("Policy updated");
      } else {
        await post("/policies", {
          name: edit.name,
          description: edit.description ?? "",
          policy_type: policyType,
          rules,
          is_active: true,
        });
        toast.success("Policy created");
      }
      await load();
      setEdit(null);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = async (p: Policy) => {
    try {
      await patch(`/policies/${p.id}`, { is_active: !p.is_active });
      toast.success(p.is_active ? "Policy deactivated" : "Policy activated");
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const remove = async (p: Policy) => {
    try {
      await del(`/policies/${p.id}`);
      toast.success("Policy deleted");
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHead
        num="05 · Rules"
        title="Policies"
        lede="Deterministic rules evaluated by the policy engine on every tool request."
        action={
          <div className="flex gap-2">
            <Button onClick={() => openNew("RISK")}>
              <Plus className="h-4 w-4" /> Add Risk Policy
            </Button>
            <Button variant="ghost" onClick={() => openNew("PARAM_DENYLIST")}>
              <Plus className="h-4 w-4" /> Add Denylist Policy
            </Button>
          </div>
        }
      />
      {!policies.length ? (
        <Empty>No policies configured. Add a RISK or PARAM_DENYLIST policy.</Empty>
      ) : (
        <div className="space-y-4">
          {policies.map((p) => (
            <article
              key={p.id}
              className="grid gap-6 border border-border bg-ivory p-6 lg:grid-cols-12"
            >
              <div className="space-y-4 lg:col-span-5">
                <div className="flex items-center gap-3">
                  <Tag v={p.policy_type} />
                  <span className="mono text-xs text-muted-foreground">{p.policy_type}</span>
                </div>
                <div>
                  <h3 className="font-serif-display text-2xl">{p.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{p.description}</p>
                </div>
                <div className="flex items-center gap-2 pt-2 text-xs">
                  <Switch
                    checked={p.is_active}
                    onCheckedChange={() => toggleActive(p)}
                    aria-label="Toggle policy enforcement"
                  />
                  <span>{p.is_active ? "Enforcing" : "Disabled"}</span>
                </div>
                <div className="flex gap-2 pt-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setEdit({
                        ...p,
                        rulesText: JSON.stringify(p.rules, null, 2),
                      })
                    }
                  >
                    <Pencil className="h-3.5 w-3.5" /> Edit
                  </Button>
                  <Confirm
                    title="Delete policy?"
                    description="This rule will stop being enforced immediately."
                    confirmLabel="Delete"
                    onConfirm={() => remove(p)}
                    trigger={
                      <Button variant="ghost" size="sm" className="text-deny">
                        <Trash2 className="h-3.5 w-3.5" /> Delete
                      </Button>
                    }
                  />
                </div>
              </div>
              <pre className="mono overflow-auto bg-brown-dark p-4 text-xs text-brown-foreground lg:col-span-7">
                {JSON.stringify(p.rules, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      )}
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-w-xl rounded-none border-border bg-ivory">
          <DialogHeader>
            <DialogTitle className="font-serif-display text-3xl">
              {edit?.id ? "Edit policy" : "New policy"}
            </DialogTitle>
          </DialogHeader>
          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <Field label="Policy Type" htmlFor="pt">
              <select
                id="pt"
                disabled={Boolean(edit?.id)}
                value={edit?.policy_type ?? "RISK"}
                onChange={(e) => {
                  const type = e.target.value as PolicyType;
                  setEdit((prev) => ({
                    ...prev,
                    policy_type: type,
                    rulesText: TEMPLATES[type],
                  }));
                }}
                className="w-full border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="RISK">RISK (Risk Level to Decision Mapping)</option>
                <option value="PARAM_DENYLIST">PARAM_DENYLIST (Regex Payload Patterns)</option>
              </select>
            </Field>
            <Field label="Name" htmlFor="pn">
              <Input
                id="pn"
                value={edit?.name ?? ""}
                onChange={(e) => setEdit({ ...edit, name: e.target.value })}
              />
            </Field>
            <Field label="Description" htmlFor="pd">
              <Input
                id="pd"
                value={edit?.description ?? ""}
                onChange={(e) => setEdit({ ...edit, description: e.target.value })}
              />
            </Field>
            <Field label="Rules (JSON)" htmlFor="pc">
              <textarea
                id="pc"
                rows={8}
                value={edit?.rulesText ?? ""}
                onChange={(e) => setEdit({ ...edit, rulesText: e.target.value })}
                className={textareaCls}
                placeholder="{}"
              />
            </Field>
            {err && <p className="text-sm text-deny">{err}</p>}
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setEdit(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? "Saving…" : "Save policy"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
