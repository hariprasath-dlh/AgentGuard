import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/auth";
import { landingRoute } from "@/lib/rbac";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — AgentGuard Control Plane" },
      {
        name: "description",
        content: "Sign in or create an AgentGuard account to govern autonomous agent activity.",
      },
      { property: "og:title", content: "Sign in — AgentGuard Control Plane" },
      {
        property: "og:description",
        content: "Sign in or create an AgentGuard account.",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { login, signup, loginWithGoogle, exchangeGoogleCode, setSessionToken, user, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Handle incoming Google OAuth redirect callback (one-time code or error in query params)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    const token = urlParams.get("token");
    const error = urlParams.get("error");

    if (error) {
      toast.error(`Google sign in failed: ${error.replace(/_/g, " ")}`);
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (code) {
      // Clear URL query parameters immediately so code never lingers in browser history
      window.history.replaceState({}, document.title, window.location.pathname);
      exchangeGoogleCode(code)
        .then(() => {
          toast.success("Signed in with Google");
        })
        .catch((err) => {
          toast.error(err instanceof Error ? err.message : "Google authentication exchange failed");
        });
    } else if (token) {
      window.history.replaceState({}, document.title, window.location.pathname);
      toast.success("Signed in with Google");
      void setSessionToken(token);
    }
  }, [exchangeGoogleCode, setSessionToken]);

  useEffect(() => {
    if (!loading && user) navigate({ to: landingRoute(user.role), replace: true });
  }, [loading, user, navigate]);

  async function onSignIn(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, password);
      toast.success("Signed in");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function onSignUp(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { needsConfirmation } = await signup({
        email,
        password,
        fullName,
        organizationName,
      });
      toast.success(
        needsConfirmation
          ? "Check your email to confirm your account."
          : "Account created — welcome to AgentGuard.",
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function onGoogle() {
    try {
      await loginWithGoogle();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Google sign in failed");
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between border-r border-border bg-sidebar px-12 py-14 lg:flex">
        <span className="font-display text-3xl tracking-tight text-brass">AgentGuard</span>
        <div>
          <h1 className="max-w-md font-display text-4xl leading-[1.15] tracking-tight">
            Every agent action, decided before it happens.
          </h1>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-muted-foreground">
            Pre-dispatch policy enforcement, spend ceilings, human-in-the-loop approvals, and a
            hash-chained audit vault that proves nothing was altered after the fact.
          </p>
        </div>
        <p className="text-[11px] tracking-[0.16em] text-muted-foreground uppercase">
          Runtime governance for autonomous systems
        </p>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <div className="panel w-full max-w-sm px-7 py-8">
          <Tabs defaultValue="signin">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="signin">Sign in</TabsTrigger>
              <TabsTrigger value="signup">Create account</TabsTrigger>
            </TabsList>

            <TabsContent value="signin">
              <form onSubmit={onSignIn}>
                <h2 className="mt-5 font-display text-2xl tracking-tight">Sign in</h2>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  Use your organization credentials.
                </p>

                <div className="mt-7 space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@company.com"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      type="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                <Button type="submit" disabled={submitting} className="mt-7 w-full">
                  {submitting ? "Signing in…" : "Sign in"}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="signup">
              <form onSubmit={onSignUp}>
                <h2 className="mt-5 font-display text-2xl tracking-tight">Create account</h2>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  Your own AgentGuard workspace, ready in seconds.
                </p>

                <div className="mt-7 space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="signup-name">Full name</Label>
                    <Input
                      id="signup-name"
                      autoComplete="name"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Ada Lovelace"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-org">Organization</Label>
                    <Input
                      id="signup-org"
                      required
                      value={organizationName}
                      onChange={(e) => setOrganizationName(e.target.value)}
                      placeholder="Acme Security"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-email">Email</Label>
                    <Input
                      id="signup-email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@company.com"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-password">Password</Label>
                    <Input
                      id="signup-password"
                      type="password"
                      autoComplete="new-password"
                      required
                      minLength={8}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="At least 8 characters"
                    />
                  </div>
                </div>

                <Button type="submit" disabled={submitting} className="mt-7 w-full">
                  {submitting ? "Creating account…" : "Create account"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>

          <div className="mt-6 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="text-[11px] tracking-[0.16em] text-muted-foreground uppercase">or</span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <Button type="button" variant="outline" className="mt-6 w-full flex items-center justify-center gap-2" onClick={onGoogle}>
            <svg className="h-4 w-4" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            Continue with Google
          </Button>
        </div>
      </div>
    </div>
  );
}
