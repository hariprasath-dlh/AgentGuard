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

interface Policy {
  id: string;
  name: string;
  description: string;
  policy_type: string;
  rules: Record<string, unknown>;
  is_active: boolean;
}

const template = JSON.stringify(
  { allowed_actions: ["read"], blocked_actions: ["delete"] },
  null,
  2,
);

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

  const save = async () => {
    setErr("");
    if (!edit?.name?.trim()) return setErr("Name is required.");
    let rules: Record<string, unknown>;
    try {
      rules = JSON.parse(edit.rulesText ?? "{}");
    } catch {
      return setErr("Rules must be valid JSON.");
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
          policy_type: "CUSTOM",
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
        num="05 · Governance"
        title="Policies"
        lede="Business rules that live in the execution path, not in a document."
        action={
          <Button onClick={() => setEdit({ rulesText: template })}>
            <Plus className="h-4 w-4" /> New policy
          </Button>
        }
      />
      {!policies.length ? (
        <Empty>No policies yet.</Empty>
      ) : (
        <div className="space-y-4">
          {policies.map((p, i) => (
            <article
              key={p.id}
              className="grid gap-6 border border-border bg-ivory p-6 lg:grid-cols-12"
            >
              <div className="lg:col-span-5">
                <div className="flex items-center gap-3">
                  <span className="font-serif-display text-3xl text-primary">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <Tag v={p.is_active ? "ACTIVE" : "INACTIVE"} />
                </div>
                <h3 className="mt-2 font-serif-display text-3xl">{p.name}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{p.description}</p>
                <div className="mt-6 flex flex-wrap items-center gap-2">
                  <label className="mr-3 flex items-center gap-2 text-sm">
                    <Switch checked={p.is_active} onCheckedChange={() => toggleActive(p)} />
                    Active
                  </label>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setEdit({ ...p, rulesText: JSON.stringify(p.rules, null, 2) })
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
                className={textareaCls}
                value={edit?.rulesText ?? ""}
                onChange={(e) => setEdit({ ...edit, rulesText: e.target.value })}
              />
            </Field>
            {err && (
              <p role="alert" className="text-sm text-deny">
                {err}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              Save policy
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
