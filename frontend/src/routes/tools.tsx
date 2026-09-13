import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import {
  EmptyState,
  ErrorState,
  PageHeader,
  Panel,
  RiskBadge,
  TableSkeleton,
} from "@/components/app/primitives";
import { AppShell } from "@/components/app/shell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, asList, type Agent, type Permission, type Tool } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canCreate, canMutate } from "@/lib/rbac";

export const Route = createFileRoute("/tools")({
  head: () => ({
    meta: [
      { title: "Tools & Permissions — AgentGuard Control Plane" },
      {
        name: "description",
        content:
          "Register callable tools, classify their risk, and grant or revoke per-agent permission to invoke them.",
      },
      { property: "og:title", content: "Tools & Permissions — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Register tools and govern which agents may call them.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="tools">
      <ToolsPage />
    </AppShell>
  ),
});

const RISKS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

function ToolsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const mayCreate = canCreate(user?.role, "tools");
  const mayMutate = canMutate(user?.role, "tools");

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Tool | null>(null);
  const [grantOpen, setGrantOpen] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", risk_level: "LOW" });
  const [grant, setGrant] = useState({ agent_id: "", tool_id: "" });

  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: async () => asList<Tool>(await api<unknown>("/tools")),
  });
  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: async () => asList<Agent>(await api<unknown>("/agents")),
  });
  const permsQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: async () => asList<Permission>(await api<unknown>("/permissions")),
  });

  const toolName = (id: string) => toolsQuery.data?.find((t) => t.id === id)?.name ?? id;
  const agentName = (id: string) => agentsQuery.data?.find((a) => a.id === id)?.name ?? id;

  const createTool = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Tool>("/tools", { method: "POST", body }),
    onSuccess: () => {
      toast.success("Tool registered");
      setCreateOpen(false);
      setForm({ name: "", description: "", risk_level: "LOW" });
      void qc.invalidateQueries({ queryKey: ["tools"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateTool = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api<Tool>(`/tools/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      toast.success("Tool updated");
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["tools"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const grantPerm = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Permission>("/permissions", { method: "POST", body }),
    onSuccess: () => {
      toast.success("Permission granted");
      setGrantOpen(false);
      setGrant({ agent_id: "", tool_id: "" });
      void qc.invalidateQueries({ queryKey: ["permissions"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const revokePerm = useMutation({
    mutationFn: ({ agentId, toolId }: { agentId: string; toolId: string }) =>
      api<void>(`/permissions/${agentId}/${toolId}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Permission revoked");
      void qc.invalidateQueries({ queryKey: ["permissions"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <PageHeader
        title="Tools & Permissions"
        subtitle="The catalogue of callable capabilities and the agents authorized to reach them."
        actions={
          mayCreate ? <Button onClick={() => setCreateOpen(true)}>+ Register Tool</Button> : null
        }
      />

      <Tabs defaultValue="tools">
        <TabsList>
          <TabsTrigger value="tools">Tools</TabsTrigger>
          <TabsTrigger value="permissions">Permissions</TabsTrigger>
        </TabsList>

        <TabsContent value="tools" className="mt-5">
          <Panel>
            {toolsQuery.isLoading ? (
              <TableSkeleton rows={5} cols={4} />
            ) : toolsQuery.isError ? (
              <ErrorState message={(toolsQuery.error as Error).message} />
            ) : (toolsQuery.data ?? []).length === 0 ? (
              <EmptyState
                title="No tools registered"
                hint="Register the capabilities your agents are allowed to reach for."
              />
            ) : (
              <div className="w-full overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                      <th className="px-5 py-3 font-medium">Tool</th>
                      <th className="px-5 py-3 font-medium">Risk</th>
                      <th className="px-5 py-3 font-medium">Active</th>
                      <th className="px-5 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {(toolsQuery.data ?? []).map((tool) => (
                      <tr key={tool.id} className="transition-colors hover:bg-surface-2/50">
                        <td className="px-5 py-3.5">
                          <span className="block text-foreground">{tool.name}</span>
                          {tool.description ? (
                            <span className="block max-w-lg truncate text-xs text-muted-foreground">
                              {tool.description}
                            </span>
                          ) : null}
                        </td>
                        <td className="px-5 py-3.5">
                          <RiskBadge level={tool.risk_level} />
                        </td>
                        <td className="px-5 py-3.5">
                          <Switch
                            checked={tool.is_active !== false}
                            disabled={!mayMutate || updateTool.isPending}
                            onCheckedChange={(checked) =>
                              updateTool.mutate({ id: tool.id, body: { is_active: checked } })
                            }
                          />
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          {mayMutate ? (
                            <Button variant="ghost" size="sm" onClick={() => setEditing(tool)}>
                              Edit
                            </Button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </TabsContent>

        <TabsContent value="permissions" className="mt-5">
          <Panel
            title="Agent → tool grants"
            actions={
              mayMutate ? (
                <Button size="sm" variant="secondary" onClick={() => setGrantOpen(true)}>
                  Grant permission
                </Button>
              ) : null
            }
          >
            {permsQuery.isLoading ? (
              <TableSkeleton rows={5} cols={3} />
            ) : permsQuery.isError ? (
              <ErrorState message={(permsQuery.error as Error).message} />
            ) : (permsQuery.data ?? []).length === 0 ? (
              <EmptyState
                title="No permissions granted"
                hint="Agents cannot call any tool until an explicit grant exists."
              />
            ) : (
              <div className="w-full overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] tracking-[0.12em] text-muted-foreground uppercase">
                      <th className="px-5 py-3 font-medium">Agent</th>
                      <th className="px-5 py-3 font-medium">Tool</th>
                      <th className="px-5 py-3 font-medium">Daily call cap</th>
                      <th className="px-5 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {(permsQuery.data ?? []).map((perm) => (
                      <tr
                        key={`${perm.agent_id}-${perm.tool_id}`}
                        className="transition-colors hover:bg-surface-2/50"
                      >
                        <td className="px-5 py-3.5 text-foreground">{agentName(perm.agent_id)}</td>
                        <td className="px-5 py-3.5 text-foreground">{toolName(perm.tool_id)}</td>
                        <td className="px-5 py-3.5 tabular-nums text-muted-foreground">
                          {perm.max_calls_per_day == null ? "Unlimited" : perm.max_calls_per_day}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          {mayMutate ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-deny hover:text-deny"
                              disabled={revokePerm.isPending}
                              onClick={() =>
                                revokePerm.mutate({
                                  agentId: perm.agent_id,
                                  toolId: perm.tool_id,
                                })
                              }
                            >
                              Revoke
                            </Button>
                          ) : null}
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

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display text-xl">Register tool</DialogTitle>
            <DialogDescription>
              Risk classification drives policy thresholds and approval routing.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="tool-name">Name</Label>
              <Input
                id="tool-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="send_wire_transfer"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tool-desc">Description</Label>
              <Textarea
                id="tool-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Initiates an outbound payment against the treasury account."
              />
            </div>
            <div className="space-y-2">
              <Label>Risk level</Label>
              <Select
                value={form.risk_level}
                onValueChange={(v) => setForm({ ...form, risk_level: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RISKS.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!form.name.trim() || createTool.isPending}
              onClick={() =>
                createTool.mutate({
                  name: form.name.trim(),
                  description: form.description.trim() || undefined,
                  risk_level: form.risk_level,
                })
              }
            >
              {createTool.isPending ? "Registering…" : "Register tool"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display text-xl">Edit tool</DialogTitle>
            <DialogDescription>
              Tools are retired with the active toggle — they are never deleted.
            </DialogDescription>
          </DialogHeader>
          {editing ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="et-name">Name</Label>
                <Input
                  id="et-name"
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="et-desc">Description</Label>
                <Textarea
                  id="et-desc"
                  value={editing.description ?? ""}
                  onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Risk level</Label>
                <Select
                  value={(editing.risk_level ?? "LOW").toUpperCase()}
                  onValueChange={(v) => setEditing({ ...editing, risk_level: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RISKS.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button
              disabled={updateTool.isPending}
              onClick={() =>
                editing &&
                updateTool.mutate({
                  id: editing.id,
                  body: {
                    name: editing.name,
                    description: editing.description ?? null,
                    risk_level: editing.risk_level,
                  },
                })
              }
            >
              {updateTool.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={grantOpen} onOpenChange={setGrantOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display text-xl">Grant permission</DialogTitle>
            <DialogDescription>
              Authorize one agent to invoke one tool. Re-granting updates the existing record.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Agent</Label>
              <Select
                value={grant.agent_id}
                onValueChange={(v) => setGrant({ ...grant, agent_id: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select an agent" />
                </SelectTrigger>
                <SelectContent>
                  {(agentsQuery.data ?? []).map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Tool</Label>
              <Select
                value={grant.tool_id}
                onValueChange={(v) => setGrant({ ...grant, tool_id: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a tool" />
                </SelectTrigger>
                <SelectContent>
                  {(toolsQuery.data ?? []).map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setGrantOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!grant.agent_id || !grant.tool_id || grantPerm.isPending}
              onClick={() =>
                grantPerm.mutate({
                  agent_id: grant.agent_id,
                  tool_id: grant.tool_id,
                  is_allowed: true,
                })
              }
            >
              {grantPerm.isPending ? "Granting…" : "Grant permission"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
