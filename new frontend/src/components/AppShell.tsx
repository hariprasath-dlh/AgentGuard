import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  Bot,
  CheckSquare,
  Grid3x3,
  Lock,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Scale,
  Settings,
  ShieldCheck,
  Vault,
  Wallet,
  Wrench,
  X,
} from "lucide-react";
import { Logo, LogoMark } from "./Logo";
import { bootstrapSession, getSession, logout, type Session } from "@/lib/auth";
import { canRead, landingRoute, type Role, type Screen } from "@/lib/rbac";
import { cn } from "@/lib/utils";
import { get } from "@/lib/api";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Activity;
  screen: Screen;
}

const nav: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: Activity, screen: "dashboard" },
  { to: "/agents", label: "Agents", icon: Bot, screen: "agents" },
  { to: "/tools", label: "Tools", icon: Wrench, screen: "tools" },
  { to: "/permissions", label: "Permissions", icon: Grid3x3, screen: "agents" },
  { to: "/policies", label: "Policies", icon: Scale, screen: "policies" },
  { to: "/budgets", label: "Budgets", icon: Wallet, screen: "budgets" },
  { to: "/approvals", label: "Approvals", icon: CheckSquare, screen: "approvals" },
  { to: "/audit", label: "Audit Vault", icon: Vault, screen: "audit" },
  { to: "/settings", label: "Settings", icon: Settings, screen: "settings" },
];

let cachedSession: Session | null = null;

export function DemoBanner() {
  return null;
}

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const [session, setSession] = useState<Session | null>(() => cachedSession ?? getSession().session);
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [pending, setPending] = useState(0);

  useEffect(() => {
    let active = true;
    const { session: localSession, expired } = getSession();

    if (!localSession) {
      cachedSession = null;
      setSession(null);
      navigate({ to: "/login", search: expired ? { expired: "1" } : {} });
      return;
    }

    cachedSession = localSession;
    setSession(localSession);

    // Bootstrap with live server state: sync role & org from /auth/me
    bootstrapSession().then((freshSession) => {
      if (!active) return;
      if (!freshSession) {
        cachedSession = null;
        setSession(null);
        navigate({ to: "/login", search: { expired: "1" } });
        return;
      }
      cachedSession = freshSession;
      setSession(freshSession);
    });

    return () => {
      active = false;
    };
  }, [navigate]);

  useEffect(() => {
    if (!session || !canRead(session.role as Role, "approvals")) {
      setPending(0);
      return;
    }

    let active = true;
    const fetchPending = () => {
      get<{ total: number }>("/hitl?status=PENDING&limit=1")
        .then((res) => {
          if (active && typeof res?.total === "number") setPending(res.total);
        })
        .catch(() => {});
    };

    fetchPending();
    const interval = setInterval(fetchPending, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [session, path]);

  useEffect(() => setOpen(false), [path]);

  const signOut = () => {
    cachedSession = null;
    logout();
    navigate({ to: "/login" });
  };

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LogoMark className="h-10 w-10 animate-pulse" />
      </div>
    );
  }

  const currentNav = nav.find((n) => n.to === path);
  const hasAccess = !currentNav || canRead(session.role as Role, currentNav.screen);
  const visibleNav = nav.filter((n) => canRead(session.role as Role, n.screen));

  const links = (compact: boolean) => (
    <nav className="flex flex-1 flex-col gap-0.5" aria-label="Control plane">
      {visibleNav.map(({ to, label, icon: Icon }) => {
        const active = path === to;
        return (
          <Link
            key={to}
            to={to}
            title={label}
            className={cn(
              "group flex items-center gap-3 px-3 py-2.5 text-sm transition-colors duration-300",
              active
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
              compact && "justify-center px-0",
            )}
          >
            <Icon className={cn("h-4 w-4 shrink-0", active && "text-primary")} />
            {!compact && <span className="flex-1">{label}</span>}
            {!compact && to === "/approvals" && pending > 0 && (
              <span className="bg-pending px-1.5 text-[0.65rem] font-bold text-ivory">
                {pending}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  const foot = (compact: boolean) => (
    <div className="border-t border-sidebar-border pt-4">
      {!compact && (
        <div className="mb-3 px-3 text-xs">
          <p className="text-sidebar-foreground">{session.name}</p>
          <p className="text-sidebar-foreground/60">
            {session.org} · {session.role}
          </p>
        </div>
      )}
      <button
        onClick={signOut}
        className={cn(
          "flex w-full items-center gap-3 px-3 py-2 text-sm text-sidebar-foreground/70 hover:text-sidebar-foreground",
          compact && "justify-center",
        )}
      >
        <LogOut className="h-4 w-4" /> {!compact && "Log out"}
      </button>
    </div>
  );

  return (
    <div className="min-h-screen">
      <DemoBanner />
      {/* Mobile top bar */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-background/95 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button aria-label="Open menu" onClick={() => setOpen(true)} className={cn("p-2")}>
          <Menu className="h-5 w-5" />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-brown-dark/50 animate-in fade-in"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col gap-6 bg-sidebar p-4 animate-in slide-in-from-left duration-300">
            <div className="flex items-center justify-between">
              <Logo
                tone="light"
                textStyle={{
                  fontFamily: "Georgia",
                  fontStyle: "italic",
                  fontWeight: "normal",
                  textDecorationLine: "none",
                }}
              />
              <button
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="p-2 text-sidebar-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {links(false)}
            {foot(false)}
          </aside>
        </div>
      )}
      <div className="flex">
        <aside
          className={cn(
            "sticky top-0 hidden h-screen shrink-0 flex-col gap-6 bg-sidebar p-4 transition-[width] duration-300 lg:flex",
            collapsed ? "w-[72px]" : "w-64",
          )}
        >
          <div
            className={cn("flex items-center", collapsed ? "justify-center" : "justify-between")}
          >
            {collapsed ? (
              <LogoMark />
            ) : (
              <Logo
                tone="light"
                textStyle={{
                  fontFamily: "Georgia",
                  fontStyle: "italic",
                  fontWeight: "normal",
                  textDecorationLine: "none",
                }}
              />
            )}
          </div>
          {links(collapsed)}
          <button
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex items-center justify-center gap-2 py-2 text-xs text-sidebar-foreground/60 hover:text-sidebar-foreground"
          >
            {collapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <>
                <PanelLeftClose className="h-4 w-4" /> Collapse
              </>
            )}
          </button>
          {foot(collapsed)}
        </aside>
        <main className="min-w-0 flex-1 px-4 py-8 sm:px-6 md:px-10 lg:py-12 xl:px-14">
          <div className="mx-auto max-w-[1400px]">
            {hasAccess ? (
              children
            ) : (
              <div className="rounded-lg border border-border bg-card p-8 text-center sm:p-12">
                <Lock className="mx-auto h-10 w-10 text-muted-foreground" />
                <h2 className="mt-4 text-xl font-semibold">Access Restricted</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Your role (<span className="font-mono font-medium text-foreground">{session.role}</span>) does not have permission to access the{" "}
                  <span className="font-medium text-foreground">{currentNav?.label}</span> screen.
                </p>
                <div className="mt-6">
                  <Link
                    to={landingRoute(session.role as Role)}
                    className="inline-flex items-center gap-2 rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Go to accessible screen
                  </Link>
                </div>
              </div>
            )}
          </div>
          <p className="mx-auto mt-16 flex max-w-[1400px] items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" /> AgentGuard · Runtime Governance Control Plane
          </p>
        </main>
      </div>
    </div>
  );
}
