# AgentGuard Frontend

AgentGuard Control Plane — Lovable Master Build Prompt (Premium Design Revision)

Paste this entire prompt into Lovable in a single message. Plan the full application internally before generating anything, then build it completely in one pass — every screen, every API integration, every RBAC state — rather than a partial scaffold that needs follow-up prompts to finish. Credits are limited; there is no budget for a second pass to "add the rest later." Build it right the first time, the way a senior product-design engineer would ship a funded security company's flagship console, not a prototype.

You are the lead frontend engineer and product designer building the complete Control Plane Dashboard for AgentGuard — a runtime governance and pre-dispatch control layer for autonomous AI agents. This is not an internal tool. It is the flagship interface of a security product, and it needs to look and feel like one: the kind of console a Fortune 500 CISO would trust on sight, not a generic admin panel.

Design Direction — Read This Before Writing Any Component

The brief is premium, cinematic, and specific — not the default AI-generated SaaS look. Do not reach for the usual patterns: no slate-and-indigo dark theme, no purple-to-blue gradient hero, no Inter-everywhere typography, no stock emerald/amber/red status colors straight out of a Tailwind palette. If a component would look at home in a generic admin-dashboard template, redesign it.

Typography. Pair an elegant display serif for the product wordmark, page titles, and large numerals with a clean geometric sans for UI text and a monospace for hashes/IDs/technical values. Use a serif such as Fraunces or Instrument Serif for "AgentGuard" itself and section headers — this is what gives the brand its premium, elegant weight, since almost no security dashboard uses serif type and it immediately reads as considered rather than templated. Use a geometric sans such as General Sans or Satoshi for body copy, labels, and controls — not Inter, not Roboto, not the default system font. Use a monospace such as IBM Plex Mono or JetBrains Mono strictly for SHA-256 hashes, request IDs, and API keys, styled distinctly (subtle background tint, tighter tracking) so technical values are visually set apart from prose. Keep the type scale restrained — a handful of deliberate sizes, generous line height, no more than two weights per font in active use anywhere on a single screen.

Color palette. Design an original palette, not a default one. Suggested direction, adjust with taste: a near-black obsidian background (not pure black, something like a very dark warm charcoal) with a subtle fine-grain texture rather than a flat fill; a warm brass/bronze accent as the brand color for the wordmark, primary buttons, and focus states, used sparingly so it reads as premium rather than loud; a cool, desaturated teal as the secondary interactive color for links, active nav states, and secondary actions. For status semantics, avoid literal Tailwind emerald/amber/red — use desaturated, deliberate variants instead: a muted sage/moss green for ALLOW and VALID, a burnished amber (not a bright warning yellow) for PENDING, a deep oxblood/rust for DENY, INVALID, and CRITICAL. Risk badges should form their own restrained gradient from a cool slate (LOW) through amber (MEDIUM) and burnt orange (HIGH) to the oxblood (CRITICAL) — recognizable at a glance without looking like a traffic light. Every color choice should feel intentional and slightly unusual, the way a boutique security or fintech brand's palette does, not like it was auto-generated.

Motion. This should feel cinematic without being gimmicky. Use smooth, physics-based transitions (Framer Motion) for page entry, modal open/close, and list item insertion — nothing snaps into place. Stat numbers on the Dashboard should animate by counting up on load, not appear instantly. Status badges for PENDING should carry a subtle, slow pulse — not a distracting blink — to communicate "awaiting action" ambiently. The Audit Vault's hash-chain visualization should render as an actual connected-link graphic (not just a table) that animates a verification pass sweeping down the chain when "Verify Chain" is clicked, settling into a solid green line if valid or visibly breaking at the tampered link if invalid — this is the single moment in the product where a little theater earns its place, because it's the literal visual proof of the product's core claim. Skeleton loading states should shimmer, not just sit static. Respect prefers-reduced-motion throughout.

Restraint. Premium does not mean busy. Generous whitespace, a strong grid, one clear focal point per screen. No unnecessary card shadows stacked on card shadows, no gratuitous gradients behind every panel. The elegance should come from typography, color discipline, spacing, and the quality of the motion — not from decoration.

Backend API & Connectivity (Verified — Do Not Deviate)

Base URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000", all business endpoints under /api/v1.

Auth header: Authorization: Bearer <access_token> on every authenticated request.

Authenticate via POST /api/v1/auth/login. Store the JWT in memory/React auth context (not casually in localStorage if you can avoid it, but localStorage is acceptable for this MVP — note the tradeoff in a code comment rather than silently picking one). On app load, call GET /api/v1/auth/me for the user profile and role.

No refresh tokens exist on this backend. On any HTTP 401, clear the token immediately, redirect to /login, and show "Session expired. Please log in again." Do not build a silent-refresh flow — there is nothing on the backend for it to call.

Real-time strategy: polling only. Poll GET /api/v1/dashboard/activity?limit=25&offset=0 every 5 seconds while the tab is active and pause when it isn't. WebSockets and SSE are explicitly out of scope — do not build them even if they'd be "nicer."

Screens — Build All Eight, Every Button Wired to a Real Endpoint

Sidebar navigation, eight screens. Every action listed below must be fully wired and functional — no dead buttons, no "coming soon" states, no navigation dead ends. If an action's endpoint doesn't exist (see the Settings note at the end), the button must not be built rather than built and left broken.

1. Dashboard — /dashboard. Visible to ADMIN, SECURITY, AUDITOR, MANAGER. Animated stat tiles from GET /api/v1/dashboard/stats: total agents, total tools, requests today, allowed/blocked/pending counts today, total spend today. A budget utilization section with progress indicators per agent (spend vs. daily cap) from the same endpoint's budget_utilization data. A live activity feed from GET /api/v1/dashboard/activity, polled every 5 seconds, with filter chips (ALL/ALLOW/DENY/PENDING), each row showing timestamp, agent, tool, decision badge, reason, and latency, expandable to show the full payload.

2. Agents — /agents. All roles read. Create: ADMIN, SECURITY, DEVELOPER. Edit/deactivate: ADMIN, SECURITY. Table from GET /api/v1/agents, joined client-side with GET /api/v1/budgets (on agent_id) to show spend and caps alongside each agent — the backend does not return this pre-joined, so this join happens in the frontend. Note: the Agent model has no "environment" field on the backend; do not fabricate one — omit that column rather than inventing data. "+ Register Agent" modal (POST /api/v1/agents) with a prominent one-time API key reveal modal on success, copy button, and an explicit warning that the key cannot be retrieved again. Edit modal (PATCH /api/v1/agents/{id}). Deactivate action (DELETE /api/v1/agents/{id}, which soft-deletes to status DELETED — label the button "Deactivate," not "Delete," since nothing is actually removed).

3. Tools & Permissions — /tools. All roles read tools. Create: ADMIN, SECURITY, DEVELOPER. Update/grant permissions: ADMIN, SECURITY. Tools table from GET /api/v1/tools (name, description, risk badge, active toggle). A permissions view joining GET /api/v1/tools, GET /api/v1/agents, and GET /api/v1/permissions client-side to show which agents may call which tools. "+ Register Tool" (POST /api/v1/tools). Edit tool (PATCH /api/v1/tools/{id}) — no delete action exists for tools by design (retirement is via the active toggle only), so do not build a delete button here. Grant/update permission (POST /api/v1/permissions), revoke (DELETE /api/v1/permissions/{agent_id}/{tool_id}).

4. Policies — /policies. Read: ADMIN, SECURITY, AUDITOR, MANAGER. Write: ADMIN, SECURITY. Table from GET /api/v1/policies (name, type, rules summary, active toggle). "+ New Policy" (POST /api/v1/policies) with structured inputs for the valid rule keys (allowed_actions, blocked_actions, risk_thresholds, max_cost_per_call) rather than a raw JSON textarea — validate client-side that at least one valid key is present before submit. Edit (PATCH /api/v1/policies/{id}). Soft-delete (DELETE /api/v1/policies/{id}).

5. Budgets — /budgets. Read: ADMIN, SECURITY, AUDITOR, MANAGER. Edit: ADMIN, SECURITY. Table from GET /api/v1/budgets, joined client-side with GET /api/v1/agents for human-readable names (the budgets endpoint returns agent_id, not a name). Show request-rate caps, session/daily cost caps, and current spend, with null caps displayed as "Unlimited," not "0" or blank. "Configure Caps" modal (PATCH /api/v1/budgets/{id}), allowing any numeric field to be cleared back to unlimited.

6. Approvals (HITL) — /approvals. Restricted to ADMIN and MANAGER; show a clear access-restricted state for other roles rather than an empty or broken screen. Pending queue from GET /api/v1/hitl?status=PENDING, joined client-side with GET /api/v1/agents for agent names since the HITL endpoint doesn't return them. Each card shows tool, agent, risk, requested parameters (JSON viewer), reason, and an expiration countdown. A history tab filters APPROVED/DENIED/EXPIRED. Approve (POST /api/v1/hitl/{id}/approve) and Deny (POST /api/v1/hitl/{id}/deny), both accepting optional review notes, both disabling immediately on click to prevent duplicate submission.

7. Audit Vault — /audit. Restricted to ADMIN and AUDITOR. A prominent "Verify Chain" action (POST /api/v1/audit/verify) driving the animated chain-verification visual described above — VALID renders as an intact, glowing chain with record count and verification time; INVALID renders the break at the exact tampered record with its sequence number and details surfaced clearly, not buried in a toast. A log table from GET /api/v1/audit?limit=50&offset=0: sequence number, timestamp, event type, decision, truncated current hash with a copy-to-clipboard action, truncated previous hash, expandable to the full event payload.

8. Settings — /settings. Accessible to all authenticated users. Show organization name, slug, and ID plus the current user's profile and role, all from GET /api/v1/auth/me — this is the only Settings data source currently confirmed on the backend. Do not build API key list/generate/revoke UI in this screen. A prior draft of this spec assumed /api/v1/auth/api-keys endpoints exist; they have not been confirmed as implemented. Ship Settings with only the organization/profile section for now, and leave a clearly marked, non-interactive placeholder section labeled "API Key Management — coming once the backend endpoint is confirmed" so the screen is honest about its current scope rather than shipping buttons that 404.

RBAC — Enforce in the UI, Matching Real Backend Enforcement

Read role from GET /api/v1/auth/me and gate navigation and actions accordingly: ADMIN has full access everywhere. SECURITY has full access to Agents, Tools, Permissions, Policies, and Budgets, read-only on the Dashboard, and no access to Approvals or the Audit Vault. AUDITOR has read-only access to Dashboard, Agents, Tools, Permissions, Policies, and Budgets, plus full access (including Verify Chain) to the Audit Vault, and no access to Approvals. MANAGER has full access to Approvals, read-only elsewhere except the Audit Vault, which it cannot access at all. DEVELOPER can read and create Agents and Tools, read Permissions, and has no access to the Dashboard's stats, Policies, Budgets, Approvals, or the Audit Vault. A role attempting to navigate to a screen it can't access should see a clear, on-brand restricted-access state, not a blank page or a silent redirect.

Engineering Baseline

Production-quality React/TypeScript, proper error boundaries, skeleton loading states (shimmering, per the motion direction above), toast notifications on every mutation (success and failure), optimistic UI only where it can be safely rolled back (not on irreversible actions like Approve/Deny — wait for the response there). No placeholder Lorem Ipsum content anywhere in the shipped build; use realistic sample copy if a state needs illustrating before real data loads.

Build this completely, end to end, in this single pass.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/3b276e2b-379e-4059-8222-a040136ed3f0).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
