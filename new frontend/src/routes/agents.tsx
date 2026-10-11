import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Pencil, Plus, Power, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Confirm, CopyButton, Empty, Field, Input, PageHead, Tag } from "@/components/kit";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { pageMeta } from "@/lib/meta";
import { get, post, patch, del } from "@/lib/api";

export const Route = createFileRoute("/agents")({
  head: () =>
    pageMeta("Agents", "Create, edit, suspend and manage AI agent identities and API keys."),
  component: () => (
    <AppShell>
      <Agents />
    </AppShell>
  ),
});

interface Agent {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
  api_key_prefix?: string;
}

interface NewAgentResp extends Agent {
  api_key: string;
}

function Agents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [edit, setEdit] = useState<Partial<Agent> | null>(null);
  const [newKey, setNewKey] = useState<{ name: string; key: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () =>
    get<Agent[]>("/agents")
      .then(setAgents)
      .catch((e: Error) => toast.error(e.message));

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!edit?.name?.trim()) {
      toast.error("Name is required");
      return;
    }
    setLoading(true);
    try {
      if (edit.id) {
        await patch(`/agents/${edit.id}`, { name: edit.name, description: edit.description });
        toast.success("Agent updated");
      } else {
        const res = await post<NewAgentResp>("/agents", {
          name: edit.name,
          description: edit.description ?? "",
          status: "ACTIVE",
        });
        setNewKey({ name: res.name, key: res.api_key });
        toast.success("Agent created — copy your API key now");
      }
      await load();
      setEdit(null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggle = async (a: Agent) => {
    const newStatus = a.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE";
    try {
      await patch(`/agents/${a.id}`, { status: newStatus });
      toast.success(newStatus === "SUSPENDED" ? `${a.name} suspended` : `${a.name} reactivated`);
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const remove = async (a: Agent) => {
    try {
      await del(`/agents/${a.id}`);
      toast.success("Agent deleted");
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHead
        num="02 · Identities"
        title="Agents"
        lede="Every agent gets an identity, an API key and a kill switch."
        action={
          <Button onClick={() => setEdit({})}>
            <Plus className="h-4 w-4" /> New agent
          </Button>
        }
      />
      {!agents.length ? (
        <Empty>No agents yet. Create your first agent to start governing tool calls.</Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {agents.map((a) => (
            <article
              key={a.id}
              className="flex flex-col border border-border bg-ivory p-6 transition-colors hover:border-foreground/40"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="mono text-xs text-muted-foreground">{a.id}</p>
                  <h3 className="mt-1 font-serif-display text-3xl">{a.name}</h3>
                </div>
                <Tag v={a.status as "ACTIVE" | "SUSPENDED"} />
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{a.description}</p>
              {a.api_key_prefix && (
                <p className="mt-2 mono text-xs text-muted-foreground">
                  Key prefix: {a.api_key_prefix}…
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
                <Link to="/permissions" className="hover:text-primary">
                  View permissions →
                </Link>
                <Link to="/budgets" className="hover:text-primary">
                  Budget →
                </Link>
              </div>
              <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-4">
                <Button variant="ghost" size="sm" onClick={() => setEdit(a)}>
                  <Pencil className="h-3.5 w-3.5" /> Edit
                </Button>
                <Confirm
                  title={a.status === "ACTIVE" ? "Engage kill switch?" : "Reactivate agent?"}
                  description={
                    a.status === "ACTIVE"
                      ? `${a.name} will be denied on every tool request immediately.`
                      : `${a.name} will resume normal evaluation.`
                  }
                  confirmLabel={a.status === "ACTIVE" ? "Suspend" : "Reactivate"}
                  onConfirm={() => toggle(a)}
                  trigger={
                    <Button
                      variant="ghost"
                      size="sm"
                      className={a.status === "ACTIVE" ? "text-deny" : "text-allow"}
                    >
                      <Power className="h-3.5 w-3.5" />{" "}
                      {a.status === "ACTIVE" ? "Kill switch" : "Reactivate"}
                    </Button>
                  }
                />
                <Confirm
                  title="Delete agent?"
                  description="The agent is soft-deleted: its key stops working, but audit records are preserved."
                  confirmLabel="Delete"
                  onConfirm={() => remove(a)}
                  trigger={
                    <Button variant="ghost" size="sm" className="text-deny">
                      <Trash2 className="h-3.5 w-3.5" /> Delete
                    </Button>
                  }
                />
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="rounded-none border-border bg-ivory">
          <DialogHeader>
            <DialogTitle className="font-serif-display text-3xl">
              {edit?.id ? "Edit agent" : "New agent"}
            </DialogTitle>
          </DialogHeader>
          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <Field label="Name" htmlFor="an">
              <Input
                id="an"
                value={edit?.name ?? ""}
                onChange={(e) => setEdit({ ...edit, name: e.target.value })}
              />
            </Field>
            <Field label="Description" htmlFor="ad">
              <Input
                id="ad"
                value={edit?.description ?? ""}
                onChange={(e) => setEdit({ ...edit, description: e.target.value })}
              />
            </Field>
            <Button type="submit" className="w-full" disabled={loading}>
              Save
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* API key reveal dialog */}
      <Dialog open={!!newKey} onOpenChange={(o) => !o && setNewKey(null)}>
        <DialogContent className="rounded-none border-border bg-ivory">
          <DialogHeader>
            <DialogTitle className="font-serif-display text-3xl">
              API key — shown once
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Copy this key now. After you close this window it can't be shown again.
          </p>
          <div className="flex flex-wrap items-center gap-2 bg-brown-dark p-3">
            <code className="mono flex-1 break-all text-xs text-brown-foreground">
              {newKey?.key}
            </code>
          </div>
          <div className="flex justify-between">
            <CopyButton value={newKey?.key ?? ""} label="Copy key" />
            <Button onClick={() => setNewKey(null)}>I've stored it</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
