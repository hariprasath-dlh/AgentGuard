import { useReducedMotion } from "framer-motion";
import { Check, Copy, ShieldAlert } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";

/* -------------------------------- layout --------------------------------- */

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 sm:mb-8">
      <div className="min-w-0">
        <h1 className="font-display text-2xl leading-tight tracking-tight text-foreground sm:text-3xl">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}


export function Panel({
  children,
  className,
  title,
  actions,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  actions?: ReactNode;
}) {
  return (
    <section className={cn("panel", className)}>
      {title || actions ? (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3.5 sm:px-5">
          <h2 className="min-w-0 font-display text-base tracking-tight text-foreground">{title}</h2>
          {actions}
        </header>

      ) : null}
      {children}
    </section>
  );
}

export function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string | undefined;
}) {
  // CSS-driven entry: renders visible even if JS animation never runs.
  return (
    <div
      className={cn("animate-in fade-in slide-in-from-bottom-2 duration-500 fill-mode-both", className)}
      style={{ animationDelay: `${delay}s` }}
    >
      {children}
    </div>
  );
}

/* -------------------------------- badges ---------------------------------- */

const decisionStyles: Record<string, string> = {
  ALLOW: "text-allow border-allow/35 bg-allow/10",
  ALLOWED: "text-allow border-allow/35 bg-allow/10",
  VALID: "text-allow border-allow/35 bg-allow/10",
  APPROVED: "text-allow border-allow/35 bg-allow/10",
  ACTIVE: "text-allow border-allow/35 bg-allow/10",
  PENDING: "text-pending border-pending/35 bg-pending/10 pulse-soft",
  DENY: "text-deny border-deny/40 bg-deny/12",
  DENIED: "text-deny border-deny/40 bg-deny/12",
  BLOCKED: "text-deny border-deny/40 bg-deny/12",
  INVALID: "text-deny border-deny/40 bg-deny/12",
  DELETED: "text-muted-foreground border-border bg-muted/40",
  EXPIRED: "text-muted-foreground border-border bg-muted/40",
  INACTIVE: "text-muted-foreground border-border bg-muted/40",
};

export function StatusBadge({
  value,
  className,
}: {
  value?: string | null | undefined;
  className?: string | undefined;
}) {
  const key = (value ?? "—").toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-[0.08em] uppercase",
        decisionStyles[key] ?? "border-border bg-muted/40 text-muted-foreground",
        className,
      )}
    >
      {key}
    </span>
  );
}

const riskStyles: Record<string, string> = {
  LOW: "text-risk-low border-risk-low/35 bg-risk-low/10",
  MEDIUM: "text-risk-medium border-risk-medium/35 bg-risk-medium/10",
  HIGH: "text-risk-high border-risk-high/40 bg-risk-high/12",
  CRITICAL: "text-risk-critical border-risk-critical/45 bg-risk-critical/14",
};

export function RiskBadge({ level }: { level?: string | null | undefined }) {
  const key = (level ?? "LOW").toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-[0.08em] uppercase",
        riskStyles[key] ?? "border-border bg-muted/40 text-muted-foreground",
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {key}
    </span>
  );
}

/* ------------------------------ technical bits ---------------------------- */

export function HashChip({
  value,
  chars = 10,
  copyable = true,
}: {
  value?: string | null | undefined;
  chars?: number;
  copyable?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-xs text-muted-foreground">—</span>;
  const short = value.length > chars ? `${value.slice(0, chars)}…` : value;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="mono-chip text-muted-foreground">{short}</span>
      {copyable ? (
        <button
          type="button"
          aria-label="Copy value"
          className="text-muted-foreground transition-colors hover:text-brass"
          onClick={() => {
            void navigator.clipboard.writeText(value);
            setCopied(true);
            toast.success("Copied to clipboard");
            setTimeout(() => setCopied(false), 1400);
          }}
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        </button>
      ) : null}
    </span>
  );
}

export function JsonBlock({ data }: { data: unknown }) {
  return (
    <pre className="max-h-72 overflow-auto rounded-md border border-border bg-background/60 p-3 font-mono text-xs leading-relaxed text-muted-foreground">
      {JSON.stringify(data ?? {}, null, 2)}
    </pre>
  );
}

export function CountUp({
  value,
  decimals = 0,
  prefix = "",
}: {
  value: number;
  decimals?: number;
  prefix?: string;
}) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(reduce ? value : 0);
  const frame = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (reduce) {
      setDisplay(value);
      return;
    }
    const start = performance.now();
    const from = 0;
    const duration = 900;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (value - from) * eased);
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [value, reduce]);

  return (
    <span>
      {prefix}
      {display.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
    </span>
  );
}

/* -------------------------------- states ---------------------------------- */

export function TableSkeleton({ rows = 6, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2 p-5">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="grid gap-3" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
          {Array.from({ length: cols }).map((__, c) => (
            <div key={c} className="shimmer h-4 rounded" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="px-5 py-14 text-center">
      <p className="font-display text-lg text-foreground">{title}</p>
      {hint ? <p className="mt-1.5 text-sm text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="px-5 py-12 text-center">
      <p className="text-sm text-deny">{message}</p>
    </div>
  );
}

export function RestrictedState({ screen }: { screen: string }) {
  return (
    <FadeIn className="mx-auto max-w-lg">
      <div className="panel mt-16 px-8 py-12 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full border border-brass/30 bg-brass-soft">
          <ShieldAlert className="size-5 text-brass" />
        </div>
        <h1 className="mt-5 font-display text-2xl tracking-tight">Access restricted</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Your role does not include permission for {screen}. Contact an organization administrator
          if you need this access.
        </p>
      </div>
    </FadeIn>
  );
}
