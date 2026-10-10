import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AuthLayout, GoogleIcon } from "@/components/AuthLayout";
import { Button, Field, Input } from "@/components/kit";
import { login, googleLoginUrl } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  validateSearch: (s: Record<string, unknown>): { expired?: string; error?: string } => ({
    expired: s.expired ? String(s.expired) : undefined,
    error: s.error ? String(s.error) : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Sign in — AgentGuard" },
      { name: "description", content: "Sign in to the AgentGuard control plane." },
      { property: "og:title", content: "Sign in — AgentGuard" },
      {
        property: "og:description",
        content: "Access the AgentGuard runtime governance control plane.",
      },
    ],
  }),
  component: Login,
});

function Login() {
  const { expired, error: urlError } = Route.useSearch();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [org, setOrg] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: string, p: string, o: string) => {
    setError("");
    setLoading(true);
    try {
      await login(e, p, o);
      toast.success("Signed in successfully");
      navigate({ to: "/dashboard" });
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  const oauthError = urlError
    ? urlError.replace(/_/g, " ")
    : undefined;

  return (
    <AuthLayout title="Welcome back." lede="Sign in to your organization's control plane.">
      {expired && (
        <div className="mb-6 border-l-2 border-pending bg-pending/10 px-4 py-3 text-sm">
          Your session expired. Please sign in again.
        </div>
      )}
      {oauthError && (
        <div className="mb-6 border-l-2 border-deny bg-deny/10 px-4 py-3 text-sm">
          Google sign-in failed: {oauthError}
        </div>
      )}
      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault();
          submit(email, password, org);
        }}
      >
        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Password" htmlFor="password">
          <div className="relative">
            <Input
              id="password"
              type={show ? "text" : "password"}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              aria-label={show ? "Hide password" : "Show password"}
              className="absolute right-0 top-1/2 -translate-y-1/2 p-2 text-muted-foreground hover:text-foreground"
            >
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </Field>
        <Field label="Organization slug (optional)" htmlFor="org">
          <Input
            id="org"
            placeholder="agentguard"
            value={org}
            onChange={(e) => setOrg(e.target.value)}
          />
        </Field>
        {error && (
          <p role="alert" className="text-sm text-deny">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" size="lg" disabled={loading}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />} Sign in
        </Button>
      </form>
      <div className="my-6 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
      </div>
      <div className="grid gap-3">
        <Button
          variant="outline"
          onClick={() => {
            window.location.href = googleLoginUrl();
          }}
        >
          <GoogleIcon /> Continue with Google
        </Button>
      </div>
      <p className="mt-8 text-sm text-muted-foreground">
        No account?{" "}
        <Link to="/register" className="font-medium text-primary hover:underline">
          Sign up
        </Link>
      </p>
    </AuthLayout>
  );
}
