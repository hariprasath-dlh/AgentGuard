import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { LogoMark } from "@/components/Logo";
import { exchangeCode } from "@/lib/auth";

export const Route = createFileRoute("/auth/callback")({
  validateSearch: (s: Record<string, unknown>): { code?: string; error?: string } => {
    const res: { code?: string; error?: string } = {};
    if (s["code"]) res.code = String(s["code"]);
    if (s["error"]) res.error = String(s["error"]);
    return res;
  },
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
  const processedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (error) {
      setMsg(`Sign-in failed: ${error}`);
      timerRef.current = setTimeout(() => navigate({ to: "/login" }), 2500);
      return;
    }

    if (!code) {
      navigate({ to: "/login" });
      return;
    }

    // Guard against React StrictMode double-execution on mount
    if (processedRef.current) {
      return;
    }
    processedRef.current = true;

    exchangeCode(code)
      .then(() => {
        navigate({ to: "/dashboard" });
      })
      .catch((err: Error) => {
        // If a valid session already exists (e.g. concurrent exchange succeeded), proceed to dashboard
        if (typeof window !== "undefined" && localStorage.getItem("ag_token")) {
          navigate({ to: "/dashboard" });
          return;
        }
        setMsg(`Sign-in failed: ${err.message}`);
        timerRef.current = setTimeout(() => navigate({ to: "/login" }), 2500);
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
