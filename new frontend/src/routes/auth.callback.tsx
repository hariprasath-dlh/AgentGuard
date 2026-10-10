import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { LogoMark } from "@/components/Logo";
import { exchangeCode } from "@/lib/auth";

export const Route = createFileRoute("/auth/callback")({
  validateSearch: (s: Record<string, unknown>): { code?: string; error?: string } => ({
    code: s.code ? String(s.code) : undefined,
    error: s.error ? String(s.error) : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Signing in — AgentGuard" },
      { name: "description", content: "Completing sign-in to AgentGuard." },
    ],
  }),
  component: Callback,
});

function Callback() {
  const navigate = useNavigate();
  const { code, error } = Route.useSearch();
  const [msg, setMsg] = useState("Completing sign-in…");

  useEffect(() => {
    if (error) {
      setMsg(`Sign-in failed: ${error}`);
      const t = setTimeout(() => navigate({ to: "/login" }), 2500);
      return () => clearTimeout(t);
    }
    if (!code) {
      navigate({ to: "/login" });
      return;
    }
    exchangeCode(code)
      .then(() => navigate({ to: "/dashboard" }))
      .catch((err: Error) => {
        setMsg(`Sign-in failed: ${err.message}`);
        setTimeout(() => navigate({ to: "/login" }), 2500);
      });
  }, [code, error, navigate]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6">
      <LogoMark className="h-12 w-12 animate-pulse" />
      <p className="font-serif-display text-3xl">Completing sign-in…</p>
      <p className="text-sm text-muted-foreground">{msg}</p>
    </div>
  );
}
