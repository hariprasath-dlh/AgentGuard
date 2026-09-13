import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";
import { landingRoute } from "@/lib/rbac";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AgentGuard — Agent Governance Control Plane" },
      {
        name: "description",
        content:
          "Sign in to the AgentGuard control plane: agent registry, policy enforcement, budgets, human approvals and a tamper-evident audit vault.",
      },
      { property: "og:title", content: "AgentGuard — Agent Governance Control Plane" },
      {
        property: "og:description",
        content: "Runtime governance and pre-dispatch control for autonomous AI agents.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    navigate({ to: user ? landingRoute(user.role) : "/login", replace: true });
  }, [loading, user, navigate]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <span className="font-display text-3xl tracking-tight text-brass">AgentGuard</span>
      <div className="shimmer h-3 w-40 rounded-full" />
    </div>
  );
}
