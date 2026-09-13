import { Link, useNavigate, useRouter, useRouterState } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  Bot,
  FileCheck2,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Settings as SettingsIcon,
  Shield,
  Wallet,
  Wrench,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { FadeIn, RestrictedState } from "@/components/app/primitives";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";
import { canRead, type Screen } from "@/lib/rbac";
import { cn } from "@/lib/utils";

const NAV: Array<{ screen: Screen; label: string; to: string; icon: typeof Activity }> = [
  { screen: "dashboard", label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
  { screen: "agents", label: "Agents", to: "/agents", icon: Bot },
  { screen: "tools", label: "Tools & Permissions", to: "/tools", icon: Wrench },
  { screen: "policies", label: "Policies", to: "/policies", icon: Shield },
  { screen: "budgets", label: "Budgets", to: "/budgets", icon: Wallet },
  { screen: "approvals", label: "Approvals", to: "/approvals", icon: FileCheck2 },
  { screen: "audit", label: "Audit Vault", to: "/audit", icon: ScrollText },
  { screen: "settings", label: "Settings", to: "/settings", icon: SettingsIcon },
];

function NavList({
  role,
  pathname,
  onNavigate,
  animate = true,
}: {
  role: string;
  pathname: string;
  onNavigate?: () => void;
  animate?: boolean;
}) {
  return (
    <nav className="flex-1 space-y-1">
      {NAV.filter((item) => canRead(role as never, item.screen)).map((item) => {
        const active = pathname.startsWith(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={cn(
              "relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-sidebar-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
            )}
          >
            {active ? (
              animate ? (
                <motion.span
                  layoutId="nav-active"
                  className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-teal"
                />
              ) : (
                <span className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-teal" />
              )
            ) : null}
            <item.icon className={cn("size-4 shrink-0", active && "text-teal")} />
            <span className="truncate">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ screen, children }: { screen: Screen; children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const router = useRouter();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) navigate({ to: "/login", replace: true });
  }, [loading, user, navigate]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="shimmer h-3 w-40 rounded-full" />
      </div>
    );
  }

  const allowed = canRead(user.role, screen);
  const currentLabel = NAV.find((n) => n.screen === screen)?.label ?? screen;

  const identity = (
    <div className="border-t border-sidebar-border pt-4">
      <p className="truncate px-3 text-sm text-foreground">{user.full_name || user.email}</p>
      <p className="px-3 text-[11px] tracking-[0.14em] text-brass uppercase">{user.role}</p>
      <button
        type="button"
        onClick={logout}
        className="mt-3 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-foreground"
      >
        <LogOut className="size-4" /> Sign out
      </button>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-4 py-6 md:flex">
        <div className="px-2">
          <span className="font-display text-2xl tracking-tight text-brass">AgentGuard</span>
          <p className="mt-1 text-[11px] tracking-[0.16em] text-muted-foreground uppercase">
            Control Plane
          </p>
        </div>

        <div className="mt-9 flex flex-1 flex-col">
          <NavList role={user.role} pathname={pathname} />
        </div>

        {identity}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-sidebar-border bg-sidebar/95 px-3 py-3 backdrop-blur md:hidden">
          <button
            type="button"
            aria-label="Go back"
            onClick={() => router.history.back()}
            className="grid size-9 shrink-0 place-items-center rounded-md border border-sidebar-border text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
          </button>

          <div className="min-w-0 text-center">
            <p className="truncate font-display text-base tracking-tight text-foreground">
              {currentLabel}
            </p>
            <p className="text-[10px] tracking-[0.16em] text-brass uppercase">AgentGuard</p>
          </div>

          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger asChild>
              <button
                type="button"
                aria-label="Open menu"
                className="grid size-9 shrink-0 place-items-center rounded-md border border-sidebar-border text-muted-foreground transition-colors hover:text-foreground"
              >
                <Menu className="size-4" />
              </button>
            </SheetTrigger>
            <SheetContent
              side="right"
              className="flex w-[17rem] flex-col border-sidebar-border bg-sidebar px-4 py-6"
            >
              <SheetTitle className="px-2 font-display text-xl tracking-tight text-brass">
                AgentGuard
              </SheetTitle>
              <div className="mt-6 flex flex-1 flex-col overflow-y-auto">
                <NavList
                  role={user.role}
                  pathname={pathname}
                  animate={false}
                  onNavigate={() => setMenuOpen(false)}
                />
              </div>
              {identity}
            </SheetContent>
          </Sheet>
        </header>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-5 sm:py-8 md:px-10 md:py-12">
          <div className="mx-auto max-w-6xl">
            {allowed ? (
              <FadeIn key={pathname}>{children}</FadeIn>
            ) : (
              <RestrictedState screen={currentLabel} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
