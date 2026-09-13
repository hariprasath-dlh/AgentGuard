# AgentGuard Control Plane — Lovable Master Build Prompt

> **Instructions for Lovable**: Copy and paste the entire prompt below into Lovable AI to generate the complete frontend application.

```markdown
You are the lead frontend engineer building the complete Control Plane Dashboard for **AgentGuard** — a mission-critical runtime governance layer and pre-dispatch control plane for autonomous AI agents.

### Product Identity & Aesthetics
- **Vibe**: Cyber-defense control room. High-contrast dark theme (slate/zinc dark palette), crisp modern typography (Inter, with JetBrains Mono for hashes, IDs, and code), and zero cartoonish elements. This is an enterprise security product, not a student CRUD application.
- **Color Semantics**:
  - `ALLOW` / `VALID` / `ACTIVE`: Emerald green (`#10B981`)
  - `PENDING`: Amber / warning yellow (`#F59E0B`)
  - `DENY` / `INVALID` / `CRITICAL` / `DELETED`: Crimson red (`#EF4444`)
  - Risk Badges: `LOW` (slate/blue), `MEDIUM` (amber), `HIGH` (orange), `CRITICAL` (violet/red)
- **Framework**: Next.js (App Router), React, TypeScript, Tailwind CSS, Lucide React icons.

---

### Backend API & Connectivity
- **Base URL**: Use `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`.
- **API Prefix**: All business resource endpoints are mounted under `/api/v1`.
- **Auth Header**: Send `Authorization: Bearer <access_token>` with all requests.
- **Session & Token Policy**:
  - Authenticate via `POST /api/v1/auth/login` (email, password, optional organization_slug).
  - Store JWT in `localStorage` / React auth context.
  - On application startup, call `GET /api/v1/auth/me` to retrieve user profile and `role` (`ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`, `DEVELOPER`).
  - **CRITICAL**: The backend does NOT have refresh tokens. When any API call receives HTTP 401 Unauthorized, immediately clear the token and redirect to `/login` with an alert message: "Session expired. Please log in again." Do not attempt silent background retries.
- **Real-Time Strategy**: WebSockets/SSE are strictly out of scope. The live activity feed must use HTTP polling against `GET /api/v1/dashboard/activity?limit=25&offset=0` every 5 seconds when the browser tab is active.

---

### Navigation & Screens to Implement

Implement a sidebar navigation layout with the following 8 screens:

#### 1. Dashboard (Overview) — `/` or `/dashboard`
- **RBAC**: Visible to `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`.
- **Top Metrics** (`GET /api/v1/dashboard/stats`):
  - Total Agents (`total_agents`), Total Tools (`total_tools`), Requests Today (`requests_today` — resets at UTC midnight).
  - Decision breakdown pills: Allowed (`allowed_today`), Blocked (`blocked_today`), Pending (`pending_today`).
  - Total Spend Today (`total_spend_today` formatted as currency).
- **Budget Utilization Section**:
  - Progress bars displaying each agent's `current_spend` vs `max_budget_per_day` from `budget_utilization`.
- **Live Activity Feed** (`GET /api/v1/dashboard/activity?limit=25`):
  - Polled every 5 seconds. Shows timestamp, Agent Name, Tool Name, Decision Badge (`ALLOW`/`DENY`/`PENDING`), Reason, and Latency (`latency_ms`).
  - Click row to expand payload drawer. Filter buttons: `ALL`, `ALLOW`, `DENY`, `PENDING`.

#### 2. Agents — `/agents`
- **RBAC**: All roles can read. Create: `ADMIN`, `SECURITY`, `DEVELOPER`. Mutate/Delete: `ADMIN`, `SECURITY`.
- **Data Display**: Table of agents from `GET /api/v1/agents`.
- **Client-Side Joining Note**: Call `GET /api/v1/budgets` and join on `agent_id` to display each agent's current spend and daily budget cap in the table.
- **Actions**:
  - "+ Register Agent" modal calling `POST /api/v1/agents`.
  - **Important One-Time API Key Display**: On agent creation, the response returns `api_key`. Show a prominent modal with a copy button warning the user: *"This API key is shown once and cannot be recovered. Store it securely."*
  - "Edit" agent modal (`PATCH /api/v1/agents/{id}`).
  - "Deactivate/Delete" button (`DELETE /api/v1/agents/{id}` — sets status to `DELETED`).

#### 3. Tools & Permissions — `/tools`
- **RBAC**: All roles can read tools. Create tool: `ADMIN`, `SECURITY`, `DEVELOPER`. Update tool / grant permissions: `ADMIN`, `SECURITY`.
- **Data Display**:
  - Tools List (`GET /api/v1/tools`): Tool Name, Description, Risk Level badge (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`), Active toggle (`is_active`).
  - Permissions Matrix / Drawer (`GET /api/v1/permissions`): Cross-references tools and agents. Shows which agents have permission to call which tools (`is_allowed`).
- **Actions**:
  - "+ Register Tool" modal (`POST /api/v1/tools`).
  - Edit Tool (`PATCH /api/v1/tools/{id}`). Note: Tools cannot be deleted to preserve audit logs; retirement is done via `is_active: false`.
  - Grant/Update Permission (`POST /api/v1/permissions` with `{ agent_id, tool_id, is_allowed }`).
  - Revoke Permission (`DELETE /api/v1/permissions/{agent_id}/{tool_id}`).

#### 4. Policies — `/policies`
- **RBAC**: Read: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`. Write: `ADMIN`, `SECURITY`.
- **Data Display**: Grid/table of policies from `GET /api/v1/policies`: Policy Name, Type (`policy_type`), Rules summary, Active toggle (`is_active`).
- **Actions**:
  - "+ New Policy" modal (`POST /api/v1/policies`).
  - **Rules JSON Validation**: The `rules` object must contain at least one valid key: `allowed_actions`, `blocked_actions`, `risk_thresholds`, or `max_cost_per_call`. Provide structured inputs for these rule types.
  - Edit Policy (`PATCH /api/v1/policies/{id}`).
  - Soft-delete Policy (`DELETE /api/v1/policies/{id}`).

#### 5. Budgets — `/budgets`
- **RBAC**: Read: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`. Edit: `ADMIN`, `SECURITY`.
- **Data Display**: Table of agent budgets from `GET /api/v1/budgets` joined with `GET /api/v1/agents`:
  - Agent Name
  - Max Requests/Min, Max Requests/Day
  - Session Budget Cap, Daily Budget Cap
  - Current Spend
- **Actions**:
  - "Configure Caps" modal calling `PATCH /api/v1/budgets/{id}` with optional numeric caps (or null for unlimited).

#### 6. Approvals (Human-in-the-Loop) — `/approvals`
- **RBAC**: Restricted to `ADMIN` and `MANAGER`. Show an access-restricted banner if other roles navigate here.
- **Data Display**: List of pending requests from `GET /api/v1/hitl?status=PENDING`:
  - Tool Name, Agent ID, Expiration countdown, Request Payload JSON viewer.
  - History Tab: Filter for `APPROVED`, `DENIED`, and `EXPIRED` requests.
- **Actions**:
  - "Approve" button (`POST /api/v1/hitl/{id}/approve` with optional `review_notes`).
  - "Deny" button (`POST /api/v1/hitl/{id}/deny` with required/optional `review_notes`).
  - Instant UI feedback: Disable buttons immediately on click to prevent duplicate submissions.

#### 7. Audit Vault — `/audit`
- **RBAC**: Restricted to `ADMIN` and `AUDITOR`.
- **Cryptographic Verification Banner**:
  - Prominent "Verify Hash Chain" button calling `POST /api/v1/audit/verify`.
  - On completion:
    - If `status === "VALID"`: Show emerald `CHAIN VALID` badge, total record count, and verification time in milliseconds.
    - If `status === "INVALID"`: Show red alert banner highlighting broken record ID, sequence number, and tamper details.
- **Audit Log Table** (`GET /api/v1/audit?limit=50&offset=0`):
  - Sequence #, Timestamp, Event Type, Decision, SHA-256 Current Hash (truncated with copy button), Previous Hash.
  - Expandable row showing full cryptographic event payload JSON.

#### 8. Settings — `/settings`
- **RBAC**: Accessible to all authenticated users.
- **Data Display**:
  - Organization Details from `GET /api/v1/auth/me` (Name, Slug, Org ID).
  - User Profile & Role badge.
  - **API Key Management** (`GET /api/v1/auth/api-keys`):
    - Table of active API keys: Key Name, Prefix (`ag_agent_...` / `ag_live_...`), Bound Agent, Created At, Expires At.
    - "Generate API Key" modal (`POST /api/v1/auth/api-keys`).
    - "Revoke Key" button (`DELETE /api/v1/auth/api-keys/{id}`).

---

### RBAC Enforcement in the UI
Always inspect `user.role` from `GET /api/v1/auth/me`:
- `ADMIN`: Full access across all screens and actions.
- `SECURITY`: Full access to Agents, Tools, Permissions, Policies, Budgets. Read-only for Dashboard. Cannot access Approvals or Audit Vault.
- `AUDITOR`: Read-only access to Dashboard, Agents, Tools, Permissions, Policies, Budgets. Full access to Audit Vault (can trigger chain verification). Cannot access Approvals.
- `MANAGER`: Full access to Approvals (can approve/deny). Read-only for Dashboard, Agents, Tools, Permissions, Policies, Budgets. Cannot access Audit Vault.
- `DEVELOPER`: Read access to Agents, Tools, Permissions. Can create agents/tools. Cannot access Dashboard stats, Policies, Budgets, Approvals, or Audit Vault.

Generate clean, robust, modern React/TypeScript components with error boundaries, loading skeletons, and toast notifications for all mutation actions.
```
