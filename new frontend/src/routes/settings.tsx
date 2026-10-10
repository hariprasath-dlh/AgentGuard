import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Loader2, LogOut, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Confirm, CopyButton, Field, Input, PageHead, Panel } from "@/components/kit";
import { getSession, logout, type Session } from "@/lib/auth";
import { pageMeta } from "@/lib/meta";
import { get, post, del } from "@/lib/api";

export const Route = createFileRoute("/settings")({
  head: () => pageMeta("Settings", "Profile, organization, API keys and service health."),
  component: () => (
    <AppShell>
      <Settings />
    </AppShell>
  ),
});

interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  expires_at: string | null;
}

interface NewKeyResp extends ApiKey {
  api_key: string;
}

function Settings() {
  const navigate = useNavigate();
  const [s, setS] = useState<Session | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [newKey, setNewKey] = useState<{ name: string; key: string } | null>(null);
  const [keyName, setKeyName] = useState("");
  const [health, setHealth] = useState<"checking" | "ok" | "error">("checking");

  useEffect(() => { setS(getSession().session); }, []);

  const loadKeys = () =>
    get<ApiKey[]>("/auth/api-keys")
      .then(setApiKeys)
      .catch(() => {});

  const checkHealth = async () => {
    setHealth("checking");
    try {
      await get("/auth/me");
      setHealth("ok");
    } catch {
      setHealth("error");
    }
  };

  useEffect(() => {
    loadKeys();
    checkHealth();
  }, []);

  const createKey = async () => {
    if (!keyName.trim()) return toast.error("Key name is required");
    try {
      const res = await post<NewKeyResp>("/auth/api-keys", { name: keyName });
      setNewKey({ name: res.name, key: res.api_key });
      setKeyName("");
      toast.success("API key created — copy it now");
      await loadKeys();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const revokeKey = async (id: string) => {
    try {
      await del(`/auth/api-keys/${id}`);
      toast.success("Key revoked");
      await loadKeys();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  if (!s) return null;

  return (
    <>
      <PageHead num="09 · Configuration" title="Settings" lede="Your profile, organization and service health." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Profile" num="A">
          <dl className="space-y-4 text-sm">
            <div>
              <dt className="eyebrow text-muted-foreground">Name</dt>
              <dd className="mt-1 font-display font-semibold">{s.name}</dd>
            </div>
            <div>
              <dt className="eyebrow text-muted-foreground">Email</dt>
              <dd className="mono mt-1">{s.email}</dd>
            </div>
            <div>
              <dt className="eyebrow text-muted-foreground">Role</dt>
              <dd className="mt-1">{s.role}</dd>
            </div>
          </dl>
        </Panel>
        <Panel title="Organization" num="B">
          <dl className="space-y-4 text-sm">
            <div>
              <dt className="eyebrow text-muted-foreground">Name</dt>
              <dd className="mt-1 font-display font-semibold">{s.orgName}</dd>
            </div>
            <div>
              <dt className="eyebrow text-muted-foreground">Slug</dt>
              <dd className="mono mt-1">{s.org}</dd>
            </div>
            <div>
              <dt className="eyebrow text-muted-foreground">Environment</dt>
              <dd className="mt-1">Active</dd>
            </div>
          </dl>
        </Panel>
        <Panel title="API keys" num="C" className="lg:col-span-2">
          <p className="text-sm text-muted-foreground">
            Keys are shown once. Store them securely.
          </p>
          {newKey && (
            <div className="mt-4 space-y-2 border border-allow p-4">
              <p className="eyebrow text-allow">New key — copy now</p>
              <code className="mono block break-all bg-brown-dark p-3 text-xs text-brown-foreground">
                {newKey.key}
              </code>
              <div className="flex justify-between">
                <CopyButton value={newKey.key} />
                <Button size="sm" variant="ghost" onClick={() => setNewKey(null)}>
                  I've stored it
                </Button>
              </div>
            </div>
          )}
          <div className="mt-4 flex gap-3">
            <Field label="Key name" htmlFor="kn" className="flex-1">
              <Input
                id="kn"
                placeholder="my-service-key"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
              />
            </Field>
            <Button className="mt-7" onClick={createKey}>
              Generate
            </Button>
          </div>
          {apiKeys.length > 0 && (
            <div className="mt-6 divide-y divide-border border border-border">
              {apiKeys.map((k) => (
                <div key={k.id} className="flex items-center justify-between p-3 text-sm">
                  <div>
                    <p className="font-display font-semibold">{k.name}</p>
                    <p className="mono text-xs text-muted-foreground">{k.key_prefix}…</p>
                  </div>
                  <Confirm
                    title="Revoke key?"
                    description="This key will stop working immediately."
                    confirmLabel="Revoke"
                    onConfirm={() => revokeKey(k.id)}
                    trigger={
                      <Button variant="ghost" size="sm" className="text-deny">
                        Revoke
                      </Button>
                    }
                  />
                </div>
              ))}
            </div>
          )}
        </Panel>
        <Panel
          title="Backend health"
          num="D"
          action={
            <Button size="sm" variant="ghost" onClick={checkHealth}>
              <RefreshCw className="h-3.5 w-3.5" /> Recheck
            </Button>
          }
        >
          <ul className="space-y-3 text-sm">
            {["Decision engine", "Policy evaluator", "Audit ledger"].map((n) => (
              <li key={n} className="flex items-center justify-between border-b border-border pb-3">
                <span>{n}</span>
                {health === "checking" ? (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                ) : health === "ok" ? (
                  <span className="flex items-center gap-2 text-allow">
                    <span className="h-2 w-2 rounded-full bg-allow" /> Operational
                  </span>
                ) : (
                  <span className="flex items-center gap-2 text-deny">
                    <span className="h-2 w-2 rounded-full bg-deny" /> Unreachable
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
      <Confirm
        title="Log out?"
        description="You'll return to the sign-in page."
        confirmLabel="Log out"
        onConfirm={() => {
          logout();
          navigate({ to: "/login" });
        }}
        trigger={
          <Button variant="outline" className="mt-8">
            <LogOut className="h-4 w-4" /> Log out
          </Button>
        }
      />
    </>
  );
}
