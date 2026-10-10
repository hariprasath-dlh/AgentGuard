import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { Logo } from "@/components/Logo";
import { btn, Tag } from "@/components/kit";
import { cn } from "@/lib/utils";
import problemImg from "@/assets/problem.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AgentGuard — Control What AI Agents Can Do" },
      {
        name: "description",
        content:
          "Runtime security and governance control plane that evaluates every AI-agent tool request before it executes.",
      },
      { property: "og:title", content: "AgentGuard — Control What AI Agents Can Do" },
      {
        property: "og:description",
        content: "The agent proposes. AgentGuard decides. The tool executes.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Home,
});

const pipeline = [
  "AUTH",
  "AGENT STATUS",
  "TOOL PERMISSION",
  "POLICY",
  "RATE LIMIT",
  "BUDGET",
  "RISK",
  "HITL REVIEW",
  "DECISION",
];

function Nav() {
  return (
    <header className="mx-auto flex max-w-[1440px] items-center justify-between px-5 py-6 md:px-10">
      <Logo />
      <nav className="hidden items-center gap-8 text-sm text-muted-foreground md:flex">
        <a href="#problem" className="hover:text-foreground">
          Problem
        </a>
        <a href="#architecture" className="hover:text-foreground">
          Architecture
        </a>
        <a href="#control-plane" className="hover:text-foreground">
          Control plane
        </a>
        <a href="#audit" className="hover:text-foreground">
          Audit
        </a>
      </nav>
      <div className="flex items-center gap-2">
        <Link
          to="/login"
          className={cn(btn({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}
        >
          Login
        </Link>
        <Link to="/dashboard" className={btn({ variant: "dark", size: "sm" })}>
          Open Control Plane
        </Link>
      </div>
    </header>
  );
}

function SectionNum({ n, label, light }: { n: string; label: string; light?: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center gap-4 border-t pt-4",
        light ? "border-brown-foreground/20" : "border-border",
      )}
    >
      <span className="font-serif-display text-3xl text-primary">{n}</span>
      <span className={cn("eyebrow", light ? "text-brown-foreground/70" : "text-muted-foreground")}>
        {label}
      </span>
    </div>
  );
}

function FlowVisual() {
  const nodes = [
    {
      label: "AI Agent",
      sub: "proposes refund · $480",
      cls: "bg-ivory text-foreground border border-border",
    },
    { label: "AgentGuard", sub: "evaluates 9 checks", cls: "bg-primary text-primary-foreground" },
    { label: "Governance", sub: "PENDING · human review", cls: "bg-teal text-teal-foreground" },
    { label: "Tool / API", sub: "payments.refund", cls: "bg-brown-dark text-brown-foreground" },
  ];
  return (
    <div className="relative mx-auto w-full max-w-md">
      <svg
        className="absolute left-1/2 top-0 h-full w-2 -translate-x-1/2"
        preserveAspectRatio="none"
        viewBox="0 0 2 100"
        aria-hidden
      >
        <line
          x1="1"
          y1="0"
          x2="1"
          y2="100"
          className="stroke-foreground/40 flow-line"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="relative flex flex-col gap-8">
        {nodes.map((n, i) => (
          <div
            key={n.label}
            className={cn(
              "rise flex items-center justify-between px-6 py-5",
              n.cls,
              i % 2 ? "ml-8 md:ml-14" : "mr-8 md:mr-14",
            )}
            style={{ animationDelay: `${200 + i * 140}ms` }}
          >
            <div>
              <p className="eyebrow opacity-70">0{i + 1}</p>
              <p className="font-display text-xl font-semibold">{n.label}</p>
            </div>
            <p className="max-w-[9rem] text-right text-xs opacity-80">{n.sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Home() {
  return (
    <div className="bg-primary p-2 md:p-4">
      <div className="bg-background">
        <Nav />

        {/* 01 HERO */}
        <section className="mx-auto grid max-w-[1440px] gap-16 px-5 pb-24 pt-10 md:px-10 lg:grid-cols-12 lg:pt-16">
          <div className="lg:col-span-7">
            <p className="eyebrow rise text-primary">Runtime governance for autonomous AI</p>
            <h1
              className="rise mt-6 font-serif-display text-[3.4rem] sm:text-7xl lg:text-[7.5rem]"
              style={{ animationDelay: "80ms" }}
            >
              Control what <em className="text-primary">AI agents</em> can do.
            </h1>
            <p
              className="rise mt-8 max-w-xl text-lg leading-relaxed text-muted-foreground"
              style={{ animationDelay: "160ms" }}
            >
              AgentGuard sits between your AI agents and the tools they use. Every tool call is
              authenticated and checked against permissions, policies, budgets, and risk levels.
              Nothing runs until AgentGuard approves it.
            </p>
            <div className="rise mt-10 flex flex-wrap gap-3" style={{ animationDelay: "240ms" }}>
              <Link to="/dashboard" className={btn({ size: "lg" })}>
                Open Control Plane <ArrowRight className="h-4 w-4" />
              </Link>
              <a href="#architecture" className={btn({ variant: "outline", size: "lg" })}>
                Explore Architecture
              </a>
            </div>
            <blockquote className="mt-16 max-w-lg border-l-2 border-primary pl-5 font-serif-display text-2xl italic leading-snug text-brown">
              “The agent proposes. AgentGuard decides. The tool executes.”
            </blockquote>
          </div>
          <div className="flex items-center lg:col-span-5">
            <FlowVisual />
          </div>
        </section>

        {/* 02 PROBLEM */}
        <section id="problem" className="mx-auto max-w-[1440px] px-5 py-24 md:px-10">
          <SectionNum n="02" label="The problem" />
          <div className="mt-12 grid gap-12 lg:grid-cols-12">
            <div className="lg:col-span-5 lg:col-start-1">
              <img
                src={problemImg}
                alt="Terracotta arches and a brass latch — a gate between action and execution"
                width={1024}
                height={1280}
                loading="lazy"
                className="aspect-[4/5] w-full object-cover"
              />
            </div>
            <div className="lg:col-span-6 lg:col-start-7">
              <h2 className="font-serif-display text-5xl md:text-7xl">
                Agents move fast.{" "}
                <span className="text-muted-foreground">Unrestricted tools move faster.</span>
              </h2>
              <ul className="mt-12 divide-y divide-border border-y border-border">
                {[
                  ["Runaway spending", "Loops and retries burn through API and payment budgets."],
                  [
                    "Unsafe tool execution",
                    "A single prompt can trigger refunds, deploys or deletions.",
                  ],
                  ["Policy violations", "Business rules live in docs, not in the execution path."],
                  ["No human oversight", "High-risk actions happen without anyone reviewing them."],
                  [
                    "Weak auditability",
                    "Logs can be edited; no one can prove what really happened.",
                  ],
                ].map(([t, d], i) => (
                  <li
                    key={t}
                    className="grid grid-cols-[3rem_1fr] gap-4 py-5 md:grid-cols-[3rem_14rem_1fr]"
                  >
                    <span className="font-display text-sm text-primary">0{i + 1}</span>
                    <span className="font-display font-semibold">{t}</span>
                    <span className="col-start-2 text-muted-foreground md:col-start-auto">{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* 03 HOW */}
        <section id="architecture" className="bg-teal py-24">
          <div className="mx-auto max-w-[1440px] px-5 md:px-10">
            <div className="flex items-center gap-4 border-t border-foreground/20 pt-4">
              <span className="font-serif-display text-3xl text-brown-dark">03</span>
              <span className="eyebrow text-brown-dark/70">How AgentGuard works</span>
            </div>
            <h2 className="mt-10 max-w-6xl font-serif-display text-5xl text-brown-dark md:text-7xl">
              <span className="block">One request. Nine stages of control.</span>
              <span className="block">Before any tool runs.</span>
            </h2>
            <ol className="mt-16 grid grid-cols-1 border-l border-t border-brown-dark/25 sm:grid-cols-3 lg:grid-cols-9">
              {pipeline.map((p, i) => (
                <li
                  key={p}
                  className="group border-b border-r border-brown-dark/25 p-5 transition-colors duration-300 hover:bg-brown-dark hover:text-brown-foreground"
                >
                  <span className="font-display text-xs opacity-60">
                    {String(i + 1).padStart(2, "0")} ·
                  </span>
                  <p className="mt-8 font-display text-lg font-semibold uppercase tracking-wide">
                    {p}
                  </p>
                </li>
              ))}
            </ol>
            <div className="mt-12 grid gap-4 sm:grid-cols-3">
              {[
                ["ALLOW", "Required checks pass. The request is permitted to execute."],
                ["PENDING", "Human approval is required. Execution waits for a decision."],
                [
                  "DENY",
                  "A required check fails. The tool call is blocked and the reason is recorded.",
                ],
              ].map(([d, t]) => (
                <div key={d} className="bg-ivory p-6">
                  <Tag v={d} />
                  <p className="mt-4 text-foreground">{t}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 04 CONTROL PLANE */}
        <section id="control-plane" className="mx-auto max-w-[1440px] px-5 py-24 md:px-10">
          <SectionNum n="04" label="The control plane" />
          <div className="mt-12 grid gap-14 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <h2 className="font-serif-display text-5xl md:text-7xl">
                One place to govern every agent.
              </h2>
              <p className="mt-6 max-w-md text-muted-foreground">
                Register agents and tools, grant permissions, write policies, cap budgets, review
                approvals and verify the audit chain.
              </p>
            </div>
            <ul className="lg:col-span-7">
              {[
                ["Agents", "/agents", "Identities, API keys, kill switch"],
                ["Tools", "/tools", "Registered endpoints and risk tiers"],
                ["Permissions", "/permissions", "Agent × tool matrix"],
                ["Policies", "/policies", "Rules as JSON, toggled live"],
                ["Budgets", "/budgets", "Spend and rate caps"],
                ["Approvals", "/approvals", "Human-in-the-loop queue"],
                ["Audit Vault", "/audit", "SHA-256 hash-chained ledger"],
              ].map(([t, to, d]) => (
                <li key={t}>
                  <Link
                    to={to}
                    className="group flex items-baseline justify-between gap-4 border-b border-border py-5 transition-colors hover:text-primary"
                  >
                    <span className="font-serif-display text-4xl md:text-5xl">{t}</span>
                    <span className="hidden text-sm text-muted-foreground sm:block">{d}</span>
                    <ArrowUpRight className="h-5 w-5 shrink-0 transition-transform duration-300 group-hover:-translate-y-1 group-hover:translate-x-1" />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* 05 HITL */}
        <section className="mx-auto max-w-[1440px] px-5 pb-24 md:px-10">
          <SectionNum n="05" label="Human in the loop" />
          <div className="mt-12 grid items-center gap-12 lg:grid-cols-12">
            <div className="order-2 lg:order-1 lg:col-span-7">
              <div className="border border-border bg-ivory">
                <div className="flex items-center justify-between border-b border-border px-6 py-4">
                  <span className="eyebrow">APPROVAL · APR-001</span>
                  <Tag v="PENDING · AWAITING REVIEW" />
                </div>
                <div className="grid gap-6 p-6 sm:grid-cols-2">
                  <div>
                    <p className="eyebrow text-muted-foreground">Agent</p>
                    <p className="mt-1 font-display font-semibold">Customer Support Agent</p>
                    <p className="eyebrow mt-5 text-muted-foreground">Tool</p>
                    <p className="mt-1 font-display font-semibold">
                      Issue Customer Refund <Tag v="HIGH RISK" className="ml-2" />
                    </p>
                    <p className="eyebrow mt-5 text-muted-foreground">Reason</p>
                    <p className="mt-1 text-sm">Policy violation: Refund exceeds the $200 limit.</p>
                  </div>
                  <pre className="mono bg-brown-dark p-4 text-xs text-brown-foreground">{`{
  "charge_id": "TXN-2048",
  "amount": 480.00,
  "currency": "USD"
}`}</pre>
                </div>
                <div className="flex flex-wrap gap-3 border-t border-border px-6 py-4">
                  <Link to="/approvals" className={btn({ variant: "allow" })}>
                    Approve &amp; Execute
                  </Link>
                  <Link to="/approvals" className={btn({ variant: "outline" })}>
                    Deny Action
                  </Link>
                </div>
              </div>
            </div>
            <div className="order-1 lg:order-2 lg:col-span-5">
              <h2 className="font-serif-display text-5xl md:text-6xl">
                High-risk actions wait for human approval.
              </h2>
              <p className="mt-6 text-muted-foreground">
                When an AI agent requests a sensitive action, AgentGuard can pause execution and ask
                an authorized reviewer to inspect the request, understand the risk, and approve or
                deny it.
              </p>
            </div>
          </div>
        </section>

        {/* 06 AUDIT */}
        <section id="audit" className="bg-brown-dark py-24 text-brown-foreground">
          <div className="mx-auto max-w-[1440px] px-5 md:px-10">
            <SectionNum n="06" label="Audit vault" light />
            <div className="mt-12 grid gap-12 lg:grid-cols-12">
              <h2 className="font-serif-display text-5xl md:text-7xl lg:col-span-5">
                Every action recorded. Every record verifiable.
              </h2>
              <div className="lg:col-span-7">
                <div className="space-y-3">
                  {[
                    ["Record 005", "DENY", "9c1e…b04a", "4f2d…7a91"],
                    ["Record 006", "DENY", "4f2d…7a91", "e81b…02cc"],
                    ["Record 007", "ALLOW", "e81b…02cc", "a7d3…5f10"],
                  ].map(([id, d, p, h]) => (
                    <div
                      key={id}
                      className="grid grid-cols-2 gap-3 border border-brown-foreground/15 p-4 text-sm sm:grid-cols-[6.5rem_5rem_1fr_1fr]"
                    >
                      <span className="font-display">{id}</span>
                      <Tag v={d} />
                      <span className="mono text-xs text-brown-foreground/60">
                        Previous record: {p}
                      </span>
                      <span className="mono text-xs text-teal">Record hash: {h}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-6 flex items-center gap-3 bg-teal px-5 py-4 text-teal-foreground">
                  <span className="h-2.5 w-2.5 rounded-full bg-allow" />
                  <span className="font-display font-semibold tracking-wide">
                    AUDIT CHAIN VERIFIED
                  </span>
                </div>
                <p className="mt-4 text-sm text-brown-foreground/60">
                  Each record is linked to the previous record using a SHA-256 hash. Verification
                  helps detect changes to the audit chain.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 07 CTA */}
        <section className="mx-auto max-w-[1440px] px-5 py-28 text-center md:px-10">
          <p className="eyebrow text-primary">07</p>
          <h2 className="mx-auto mt-6 max-w-5xl font-serif-display text-6xl md:text-8xl">
            Let agents act. <em className="text-primary">Keep humans in control.</em>
          </h2>
          <Link to="/dashboard" className={cn(btn({ size: "lg" }), "mt-12")}>
            Open Control Plane <ArrowRight className="h-4 w-4" />
          </Link>
        </section>

        <footer className="border-t border-border">
          <div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-5 py-12 md:flex-row md:items-start md:justify-between md:px-10">
            <div>
              <Logo />
              <p className="mt-3 max-w-xs text-sm text-muted-foreground">
                Runtime security &amp; governance control plane for autonomous AI agents.
              </p>
            </div>
            <nav className="grid grid-cols-2 gap-y-3 gap-x-12 text-sm sm:grid-cols-3">
              <a href="#architecture" className="hover:text-primary">
                Product
              </a>
              <Link to="/dashboard" className="hover:text-primary">
                Control Plane
              </Link>
              <a href="#architecture" className="hover:text-primary">
                Documentation
              </a>
              <Link to="/settings" className="hover:text-primary">
                Settings
              </Link>
              <Link to="/login" className="hover:text-primary">
                Login
              </Link>
              <Link to="/register" className="hover:text-primary">
                Register
              </Link>
            </nav>
          </div>
          <p className="mx-auto max-w-[1440px] px-5 pb-8 text-xs text-muted-foreground md:px-10">
            © 2026 AgentGuard · Preview build
          </p>
        </footer>
      </div>
    </div>
  );
}
