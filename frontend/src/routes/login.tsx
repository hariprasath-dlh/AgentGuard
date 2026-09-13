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
  const { login, signup, loginWithGoogle, user, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [submitting, setSubmitting] = useState(false);

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

          <Button type="button" variant="outline" className="mt-6 w-full" onClick={onGoogle}>
            Continue with Google
          </Button>
        </div>
      </div>
    </div>
  );
}
