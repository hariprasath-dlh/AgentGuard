import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Confirm, Field, Input, PageHead, Tag, selectCls } from "@/components/kit";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { pageMeta } from "@/lib/meta";
import { get, post, patch } from "@/lib/api";

export const Route = createFileRoute("/tools")({
  head: () => pageMeta("Tools", "Register the tools and APIs agents may call, with risk tiers."),
  component: () => (
    <AppShell>
      <Tools />
    </AppShell>
  ),
});

interface Tool {
  id: string;
  name: string;
  description: string;
  risk_level: string;
  is_active: boolean;
}

type EditState = Partial<Tool>;

function Tools() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [edit, setEdit] = useState<EditState | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () =>
    get<Tool[]>("/tools")
      .then(setTools)
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
        await patch(`/tools/${edit.id}`, {
          name: edit.name,
          description: edit.description,
          risk_level: edit.risk_level,
        });
        toast.success("Tool updated");
      } else {
        await post("/tools", {
          name: edit.name,
          description: edit.description ?? "",
          risk_level: edit.risk_level ?? "LOW",
          is_active: true,
        });
        toast.success("Tool registered");
      }
      await load();
      setEdit(null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = async (t: Tool) => {
    try {
      await patch(`/tools/${t.id}`, { is_active: !t.is_active });
      toast.success(t.is_active ? "Tool retired" : "Tool reactivated");
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHead
        num="03 · Registry"
        title="Tools"
        lede="Agents can only reach tools registered here."
        action={
          <Button onClick={() => setEdit({ risk_level: "LOW" })}>
            <Plus className="h-4 w-4" /> Register tool
          </Button>
        }
      />
      <div className="overflow-x-auto border border-border bg-ivory">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="eyebrow border-b border-border text-left text-muted-foreground">
            <tr>
              <th className="p-4">Tool</th>
              <th className="p-4">Risk</th>
              <th className="p-4">Status</th>
              <th className="p-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {tools.map((t) => (
              <tr key={t.id} className="transition-colors hover:bg-secondary/50">
                <td className="p-4">
                  <p className="font-display font-semibold">{t.name}</p>
                  <p className="text-xs text-muted-foreground">{t.description}</p>
                </td>
                <td className="p-4">
                  <Tag v={t.risk_level as "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"} />
                </td>
                <td className="p-4">
                  <Tag v={t.is_active ? "ACTIVE" : "RETIRED"} />
                </td>
                <td className="p-4 text-right">
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setEdit(t)}>
                      <Pencil className="h-3.5 w-3.5" /> Edit
                    </Button>
                    <Confirm
                      title={t.is_active ? "Retire tool?" : "Reactivate tool?"}
                      description={
                        t.is_active
                          ? "All requests to this tool will be denied."
                          : "The tool becomes callable again for permitted agents."
                      }
                      confirmLabel={t.is_active ? "Retire" : "Reactivate"}
                      onConfirm={() => toggleActive(t)}
                      trigger={
                        <Button variant="ghost" size="sm">
                          {t.is_active ? "Retire" : "Reactivate"}
                        </Button>
                      }
                    />
                  </div>
                </td>
              </tr>
            ))}
            {!tools.length && (
              <tr>
                <td colSpan={4} className="p-8 text-center text-muted-foreground">
                  No tools registered yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="rounded-none border-border bg-ivory">
          <DialogHeader>
            <DialogTitle className="font-serif-display text-3xl">
              {edit?.id ? "Edit tool" : "Register tool"}
            </DialogTitle>
          </DialogHeader>
          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <Field label="Name" htmlFor="tn">
              <Input
                id="tn"
                placeholder="payments.refund"
                value={edit?.name ?? ""}
                onChange={(e) => setEdit({ ...edit, name: e.target.value })}
              />
            </Field>
            <Field label="Description" htmlFor="td">
              <Input
                id="td"
                value={edit?.description ?? ""}
                onChange={(e) => setEdit({ ...edit, description: e.target.value })}
              />
            </Field>
            <Field label="Risk level" htmlFor="tr">
              <select
                id="tr"
                className={selectCls}
                value={edit?.risk_level ?? "LOW"}
                onChange={(e) => setEdit({ ...edit, risk_level: e.target.value })}
              >
                {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </Field>
            <Button type="submit" className="w-full" disabled={loading}>
              Save
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
