import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Check, Minus } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Confirm, Empty, PageHead, Tag } from "@/components/kit";
import { pageMeta } from "@/lib/meta";
import { cn } from "@/lib/utils";
import { get, post, del } from "@/lib/api";

export const Route = createFileRoute("/permissions")({
  head: () => pageMeta("Permissions", "Grant and revoke which agents may call which tools."),
  component: () => (
    <AppShell>
      <Permissions />
    </AppShell>
  ),
});

interface Agent {
  id: string;
  name: string;
  status: string;
}

interface Tool {
  id: string;
  name: string;
  risk_level: string;
  is_active: boolean;
}

interface Permission {
  id: string;
  agent_id: string;
  tool_id: string;
  is_allowed: boolean;
}

function Permissions() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [perms, setPerms] = useState<Permission[]>([]);
  const [view, setView] = useState<"matrix" | "table">("matrix");

  const load = async () => {
    try {
      const [a, t, p] = await Promise.all([
        get<Agent[]>("/agents"),
        get<Tool[]>("/tools"),
        get<Permission[]>("/permissions"),
      ]);
      setAgents(a.filter((x) => x.status !== "DELETED"));
      setTools(t.filter((x) => x.is_active));
      setPerms(p);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  useEffect(() => { load(); }, []);

  const has = (agentId: string, toolId: string) =>
    perms.some((p) => p.agent_id === agentId && p.tool_id === toolId && p.is_allowed);

  const grant = async (agentId: string, toolId: string) => {
    try {
      await post("/permissions", { agent_id: agentId, tool_id: toolId, is_allowed: true });
      const tool = tools.find((t) => t.id === toolId);
      const agent = agents.find((a) => a.id === agentId);
      toast.success(`Granted ${tool?.name} to ${agent?.name}`);
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const revoke = async (agentId: string, toolId: string) => {
    try {
      await del(`/permissions/${agentId}/${toolId}`);
      const tool = tools.find((t) => t.id === toolId);
      const agent = agents.find((a) => a.id === agentId);
      toast.success(`Revoked ${tool?.name} from ${agent?.name}`);
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHead
        num="04 · RBAC"
        title="Permissions"
        lede="Default deny. An agent can only call a tool you've explicitly granted."
        action={
          <div className="flex border border-border">
            {(["matrix", "table"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={cn(
                  "eyebrow px-4 py-2.5 transition-colors",
                  view === v ? "bg-foreground text-background" : "hover:bg-secondary",
                )}
              >
                {v}
              </button>
            ))}
          </div>
        }
      />
      {view === "matrix" ? (
        <div className="overflow-x-auto border border-border bg-ivory">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="eyebrow sticky left-0 bg-ivory p-4 text-left text-muted-foreground">
                  Agent \ Tool
                </th>
                {tools.map((t) => (
                  <th key={t.id} className="p-3 text-center align-bottom">
                    <p className="mono text-xs">{t.name}</p>
                    <Tag v={t.risk_level as "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"} className="mt-1" />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {agents.map((a) => (
                <tr key={a.id}>
                  <td className="sticky left-0 bg-ivory p-4 font-display font-semibold">
                    {a.name}
                  </td>
                  {tools.map((t) => {
                    const on = has(a.id, t.id);
                    return (
                      <td key={t.id} className="p-2 text-center">
                        <button
                          aria-label={`${on ? "Revoke" : "Grant"} ${t.name} for ${a.name}`}
                          aria-pressed={on}
                          onClick={() => (on ? revoke(a.id, t.id) : grant(a.id, t.id))}
                          className={cn(
                            "inline-flex h-10 w-10 items-center justify-center border transition-all duration-300",
                            on
                              ? "border-allow bg-allow text-ivory"
                              : "border-border text-muted-foreground hover:border-foreground",
                          )}
                        >
                          {on ? <Check className="h-4 w-4" /> : <Minus className="h-4 w-4" />}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
              {!agents.length && (
                <tr>
                  <td colSpan={tools.length + 1} className="p-8 text-center text-muted-foreground">
                    No agents or tools yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : perms.length === 0 ? (
        <Empty>No permissions granted.</Empty>
      ) : (
        <div className="divide-y divide-border border border-border bg-ivory">
          {perms.map((p) => {
            const agent = agents.find((a) => a.id === p.agent_id);
            const tool = tools.find((t) => t.id === p.tool_id);
            return (
              <div
                key={p.id}
                className="flex flex-wrap items-center justify-between gap-3 p-4"
              >
                <p>
                  <span className="font-display font-semibold">
                    {agent?.name ?? p.agent_id}
                  </span>{" "}
                  <span className="mono text-xs text-muted-foreground">
                    → {tool?.name ?? p.tool_id}
                  </span>
                </p>
                <Confirm
                  title="Revoke permission?"
                  description="Future requests for this tool will be denied."
                  confirmLabel="Revoke"
                  onConfirm={() => revoke(p.agent_id, p.tool_id)}
                  trigger={
                    <Button variant="ghost" size="sm" className="text-deny">
                      Revoke
                    </Button>
                  }
                />
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
