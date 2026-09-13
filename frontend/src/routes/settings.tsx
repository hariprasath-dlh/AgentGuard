import { createFileRoute } from "@tanstack/react-router";

import { PageHeader, Panel } from "@/components/app/primitives";
import { AppShell } from "@/components/app/shell";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — AgentGuard Control Plane" },
      {
        name: "description",
        content: "Organization details and your AgentGuard profile and role assignment.",
      },
      { property: "og:title", content: "Settings — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Organization details and your AgentGuard profile and role.",
      },
    ],
  }),
  component: () => (
    <AppShell screen="settings">
      <SettingsPage />
    </AppShell>
  ),
});

function Row({ label, value }: { label: string; value?: string | null | undefined }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{value || "—"}</span>
    </div>
  );
}

function SettingsPage() {
  const { user } = useAuth();
  const orgName = user?.organization?.name ?? user?.organization_name;
  const orgSlug = user?.organization?.slug ?? user?.organization_slug;
  const orgId = user?.organization?.id ?? user?.organization_id;

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Organization and account details resolved from your active session."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Organization">
          <Row label="Name" value={orgName} />
          <Row label="Slug" value={orgSlug} />
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <span className="text-sm text-muted-foreground">Organization ID</span>
            <span className="mono-chip text-muted-foreground">{orgId || "—"}</span>
          </div>
        </Panel>

        <Panel title="Your profile">
          <Row label="Name" value={user?.full_name} />
          <Row label="Email" value={user?.email} />
          <Row label="Role" value={user?.role} />
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <span className="text-sm text-muted-foreground">User ID</span>
            <span className="mono-chip text-muted-foreground">{user?.id || "—"}</span>
          </div>
        </Panel>
      </div>

      <div className="panel mt-6 border-dashed px-5 py-6 opacity-70">
        <p className="font-display text-base tracking-tight">
          API Key Management — coming once the backend endpoint is confirmed
        </p>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Listing, generating and revoking organization API keys is not exposed by the API yet.
          Agent keys are issued once at registration on the Agents screen.
        </p>
      </div>
    </>
  );
}
