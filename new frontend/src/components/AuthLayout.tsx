import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { Logo } from "./Logo";
import { DemoBanner } from "./AppShell";
import { btn } from "./kit";
import { cn } from "@/lib/utils";

export function AuthLayout({
  title,
  lede,
  children,
}: {
  title: ReactNode;
  lede: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <DemoBanner />
      <div className="grid min-h-screen lg:grid-cols-2">
        <aside className="relative hidden flex-col justify-between bg-brown-dark p-12 text-brown-foreground lg:flex">
          <Logo tone="light" />
          <div>
            <p className="eyebrow text-peach">Runtime governance</p>
            <p className="mt-6 font-serif-display text-6xl leading-[1.02]">
              The agent proposes. <em className="text-primary">AgentGuard decides.</em>
            </p>
          </div>
          <p className="text-sm text-brown-foreground/60">Autonomous AI safety and compliance</p>
        </aside>
        <main className="relative flex items-center justify-center px-5 py-12 sm:px-10">
          <div className="absolute top-5 right-5 sm:top-8 sm:right-10 z-10">
            <Link
              to="/"
              className={cn(
                btn({ variant: "outline", size: "sm" }),
                "gap-2 text-xs font-medium border-border hover:bg-secondary transition-colors",
              )}
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to home</span>
            </Link>
          </div>
          <div className="w-full max-w-md pt-6 sm:pt-0">
            <div className="mb-8 flex items-center justify-between lg:hidden">
              <Logo />
            </div>
            <h1 className="font-serif-display text-5xl">{title}</h1>
            <p className="mt-3 text-muted-foreground">{lede}</p>
            <div className="mt-10">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}

export function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path
        fill="currentColor"
        d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3ZM12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22Zm-5.6-8c-.2-.6-.3-1.3-.3-2s.1-1.4.3-2V7.4H3.1a10 10 0 0 0 0 9.2L6.4 14ZM12 5.9c1.5 0 2.8.5 3.8 1.5l2.9-2.9A10 10 0 0 0 3.1 7.4L6.4 10C7.2 7.7 9.4 5.9 12 5.9Z"
      />
    </svg>
  );
}
