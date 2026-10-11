import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Check, Circle, Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AuthLayout, GoogleIcon } from "@/components/AuthLayout";
import { Button, Field, Input, selectCls } from "@/components/kit";
import { register, googleLoginUrl } from "@/lib/auth";
import { passwordChecks, passwordStrength } from "@/lib/password";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — AgentGuard" },
      { name: "description", content: "Create an AgentGuard organization." },
      { property: "og:title", content: "Create account — AgentGuard" },
      {
        property: "og:description",
        content: "Register your organization on the AgentGuard control plane.",
      },
    ],
  }),
  component: Register,
});

const meter = ["bg-deny", "bg-deny", "bg-pending", "bg-info", "bg-allow"];

function Register() {
  const navigate = useNavigate();
  const [f, setF] = useState({
    name: "",
    email: "",
    password: "",
    orgName: "",
    org: "",
    role: "ADMIN",
  });
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const st = passwordStrength(f.password);
  const set =
    (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setF((p) => ({ ...p, [k]: e.target.value }));
    };

  return (
    <AuthLayout
      title="Create your organization."
      lede="Set up your organization workspace to get started."
    >
      <form
        className="space-y-6"
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          if (!st.valid) return setError("Password does not meet all requirements.");
          if (!/^[a-z0-9-]{3,}$/.test(f.org))
            return setError("Slug must be 3+ lowercase letters, numbers or dashes.");
          setLoading(true);
          try {
            await register({ ...f });
            toast.success("Organization created");
            navigate({ to: "/dashboard" });
          } catch (err) {
            setError((err as Error).message);
            setLoading(false);
          }
        }}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="Full name" htmlFor="name">
            <Input id="name" required value={f.name} onChange={set("name")} />
          </Field>
          <Field label="Email" htmlFor="email">
            <Input id="email" type="email" required value={f.email} onChange={set("email")} />
          </Field>
        </div>
        <Field label="Password" htmlFor="password">
          <div className="relative">
            <Input
              id="password"
              type={show ? "text" : "password"}
              required
              value={f.password}
              onChange={set("password")}
              className="pr-10"
              aria-describedby="pw-rules"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              aria-label={show ? "Hide password" : "Show password"}
              className="absolute right-0 top-1/2 -translate-y-1/2 p-2 text-muted-foreground"
            >
              {show ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            </button>
          </div>
        </Field>
        {f.password && (
          <div id="pw-rules" className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex flex-1 gap-1">
                {[1, 2, 3, 4, 5].map((i) => (
                  <span
                    key={i}
                    className={cn(
                      "h-1 flex-1 transition-colors duration-300",
                      i <= st.score ? meter[st.score - 1] : "bg-border",
                    )}
                  />
                ))}
              </div>
              <span className="eyebrow w-14 text-right">{st.label}</span>
            </div>
            <ul className="grid gap-1 text-xs sm:grid-cols-2">
              {passwordChecks.map((c) => {
                const ok = c.test(f.password);
                return (
                  <li
                    key={c.id}
                    className={cn(
                      "flex items-center gap-2",
                      ok ? "text-allow" : "text-muted-foreground",
                    )}
                  >
                    {ok ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-3 w-3" />}{" "}
                    {c.label}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="Organization name" htmlFor="orgName">
            <Input id="orgName" required value={f.orgName} onChange={set("orgName")} />
          </Field>
          <Field label="Organization slug" htmlFor="org">
            <Input id="org" required placeholder="acme-ai" value={f.org} onChange={set("org")} />
          </Field>
        </div>
        <Field label="Role" htmlFor="role">
          <select id="role" className={selectCls} value={f.role} onChange={set("role")}>
            <option value="ADMIN">Admin</option>
            <option value="OPERATOR">Operator</option>
            <option value="REVIEWER">Reviewer</option>
            <option value="VIEWER">Viewer</option>
          </select>
        </Field>
        {error && (
          <p role="alert" className="text-sm text-deny">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={loading}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />} Create account
        </Button>
      </form>
      <Button
        variant="outline"
        className="mt-3 w-full"
        onClick={() => {
          window.location.href = googleLoginUrl();
        }}
      >
        <GoogleIcon /> Continue with Google
      </Button>
      <p className="mt-8 text-sm text-muted-foreground">
        Already registered?{" "}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
