# MASTER PROMPT: FRONTEND SPECIFICATION & FEATURE REQUIREMENTS FOR AGENTGUARD

> **Role & Purpose**: You are an expert Full-Stack Software Engineer and Systems Architect building a modern, enterprise-grade, comprehensive web application (Control Plane Dashboard) for **AgentGuard** — a pre-dispatch runtime governance and security control plane for Autonomous AI Agents.
> 
> **Instructions for the AI Model**: Implement every single page, button, form, workflow, data model, navigation path, and RBAC control listed in this prompt. Do NOT leave out any feature. This specification strictly defines the **functional features, pages, buttons, interactions, data schemas, API integrations, and navigation order**. You have full freedom on visual styling, layout aesthetics, and design theme, but every functional requirement detailed below is **mandatory**.

---

## 1. SYSTEM OVERVIEW & BACKEND ARCHITECTURE CONTRACT

### 1.1 Core Mission
AgentGuard sits between AI agents (OpenAI, LangChain, CrewAI, AutoGen, custom Python) and tools/APIs. It evaluates proposed actions *before* execution against RBAC, policy rules, spending caps, rate limits, parameter sanity, and risk tiers.
- **Golden Rule**: *The agent proposes. AgentGuard decides. The tool executes ONLY after AgentGuard allows it.*
- **Decisions**: `ALLOW` (Safe to run), `DENY` (Blocked by security/budget/risk), `PENDING` (Paused for Human-in-the-Loop approval).
- **Tamper-Evident Ledger**: Every decision is written to a SHA-256 cryptographic hash-chain audit log.

### 1.2 Global Networking & API Conventions
- **Base API URL**: Configurable via environment variable (default: `http://localhost:8000`).
- **Endpoint Prefix**: All resource endpoints are prefixed with `/api/v1`.
- **System Health Endpoints**:
  - `GET /health` → Returns `{"status": "healthy"}`
  - `GET /ready` → Returns `{"status": "ready"}`
- **Authentication Header**: Every authenticated request must include:
  ```http
  Authorization: Bearer <jwt_access_token>
  Content-Type: application/json
  ```
- **Multi-Tenant Scoping**: All database queries are strictly scoped to the user's `organization_id` extracted server-side from the JWT token. The frontend never needs to pass `organization_id` in path or query parameters.
- **Token Expiration & 401 Interceptor**:
  - Backend JWT tokens expire after 60 minutes (`expires_in: 3600`).
  - There are **no refresh tokens**.
  - When any API call returns `401 Unauthorized`: Immediately clear stored token & session state, and redirect user to `/login` with an informational message (`"Your session has expired. Please log in again."`).

---

## 2. ROLE-BASED ACCESS CONTROL (RBAC) MATRIX

The system contains 5 distinct enterprise roles. The UI must conditionally show/hide, enable/disable buttons, tabs, and action menus based on `current_user.role`:

| Feature / Resource | ADMIN | SECURITY | AUDITOR | MANAGER | DEVELOPER |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **View Dashboard Stats & Feed** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ❌ Restricted |
| **Create Agent & Provision Key** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ✅ Full |
| **View Agents List & Details** | ✅ Full | ✅ Full | ✅ View-Only | ✅ View-Only | ✅ View-Only |
| **Update Agent / Kill-Switch (Suspend)** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| **Soft-Delete Agent** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| **Create Tool & Set Risk Level** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ✅ Full |
| **View Tools List & Details** | ✅ Full | ✅ Full | ✅ View-Only | ✅ View-Only | ✅ View-Only |
| **Update Tool / Retire Tool (Deactivate)**| ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| **Grant / Revoke Tool Permissions** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| **View Permissions Matrix** | ✅ Full | ✅ Full | ✅ View-Only | ✅ View-Only | ✅ View-Only |
| **Create / Update / Delete Policies** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| **View Policies** | ✅ Full | ✅ Full | ✅ View-Only | ✅ View-Only | ❌ Hidden |
| **Configure Budget Caps & Rates** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| **View Budgets & Spend** | ✅ Full | ✅ Full | ✅ View-Only | ✅ View-Only | ❌ Hidden |
| **Review / Approve / Deny HITL Queue** | ✅ Full | ❌ Hidden | ❌ Hidden | ✅ Full | ❌ Hidden |
| **View HITL Approvals Queue** | ✅ Full | ❌ Hidden | ❌ Hidden | ✅ Full | ❌ Hidden |
| **View Cryptographic Audit Vault** | ✅ Full | ❌ Hidden | ✅ Full | ❌ Hidden | ❌ Hidden |
| **Trigger Hash-Chain Verification** | ✅ Full | ❌ Hidden | ✅ Full | ❌ Hidden | ❌ Hidden |
| **Manage Organization API Keys** | ✅ Full | ✅ Full | ❌ Hidden | ❌ Hidden | ✅ Full |

---

## 3. COMPLETE SITE MAP & NAVIGATION FLOW

```
[ Public Routes ]
├── /login ─────────────── Standard Email/Password Sign-In + Google OAuth
├── /register ──────────── Organization & User Registration
└── /auth/callback ─────── Google OAuth Token Exchange Handling

[ Protected App Shell (Requires Valid JWT) ]
├── Top Navigation Bar
│   ├── Organization Name & Slug Badge
│   ├── Backend Health Status Indicator (Polling /health)
│   ├── Quick Notification / Pending Approvals Counter Badge
│   └── User Profile Dropdown Menu (User Name, Email, Role Badge, Settings Link, Log Out Button)
│
├── Left Sidebar Navigation
│   ├── 1. Dashboard (`/dashboard`) ────────── Real-time Metrics & Activity Feed
│   ├── 2. Agents (`/agents`) ──────────────── Agent Registry, Kill-Switch, API Keys
│   ├── 3. Tools & Registry (`/tools`) ────── Tool Registry & Risk Classification
│   ├── 4. Permissions (`/permissions`) ───── Agent-Tool RBAC Grant/Revoke Matrix
│   ├── 5. Policies (`/policies`) ─────────── Deterministic Guardrail Rules (Regex/Risk)
│   ├── 6. Budgets (`/budgets`) ───────────── Cost & Rate Limit Caps per Agent
│   ├── 7. Approvals (`/approvals`) ───────── Human-in-the-Loop (HITL) Queue
│   ├── 8. Audit Vault (`/audit`) ─────────── Immutable SHA-256 Ledger & Chain Verifier
│   └── 9. Settings (`/settings`) ────────── Organization Info, API Keys, Profile, Logout
```

---

## 4. DETAILED PAGE-BY-PAGE FEATURE SPECIFICATIONS

### PAGE 1: SIGN IN (`/login`)
- **Route**: `/login` (Public route. Redirects to `/dashboard` if already authenticated).
- **Core Features**:
  1. **Email & Password Login Form**:
     - Fields:
       - `Email` (text input, validated format, normalized to lowercase).
       - `Password` (password input with toggle show/hide visibility).
       - `Organization Slug` (optional text input; for users belonging to specific workspaces).
     - Submit Action: `POST /api/v1/auth/login`
       - Payload: `{"email": "...", "password": "...", "organization_slug": "..."}`
       - Success: Receives `{"access_token": "...", "token_type": "bearer", "expires_in": 3600}`.
       - Stores token securely and immediately invokes `GET /api/v1/auth/me` to store user identity & role in state.
       - Redirects user to `/dashboard`.
       - Error States: Inline error alerts for invalid credentials (401), account inactive (403), or network failure.
  2. **Google OAuth 2.0 Sign-In Button**:
     - Action: Click initiates `GET /api/v1/auth/google/login?redirect_target=/login`.
     - Opens Google consent screen.
     - Upon redirect back to `/login?code=<exchange_code>`, the frontend detects the `code` query param and executes:
       - Action: `POST /api/v1/auth/google/exchange` with `{"code": "<exchange_code>"}`.
       - Success: Stores JWT token, calls `/auth/me`, and redirects to `/dashboard`.
       - Error Handling: Displays friendly banners for errors like `token_verification_failed`, `invalid_or_expired_state`, or `account_inactive`.
  3. **Navigation Links**:
     - Button / Link: `"Don't have an account? Sign Up"` → navigates to `/register`.
     - Informational Alert Banner: Shown if redirected with `?session_expired=true`.

---

### PAGE 2: SIGN UP / REGISTRATION (`/register`)
- **Route**: `/register` (Public route).
- **Core Features**:
  1. **New User & Organization Form**:
     - Fields:
       - `Full Name` (required text input).
       - `Email Address` (required email input, validated format).
       - `Password` (required password input with real-time strength validation checklist: ≥8 characters, 1 uppercase, 1 lowercase, 1 number).
       - `Organization Name` (optional; if left blank, automatically derived).
       - `Organization Slug` (optional; if entering an existing org slug, joins that workspace; if new slug, provisions new org).
       - `Role Selection` (optional dropdown: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`, `DEVELOPER`; defaults to `ADMIN` for first org user, `DEVELOPER` otherwise).
     - Submit Action: `POST /api/v1/auth/register`
       - Payload: `{"email": "...", "password": "...", "full_name": "...", "organization_name": "...", "organization_slug": "...", "role": "..."}`
       - Success (201 Created): Shows success notification, automatically logs in or redirects to `/login` with success banner.
       - Error States: 409 Conflict if email is already registered, 422 if password does not meet criteria.
  2. **Google OAuth Sign-Up Option**:
     - Button: `"Continue with Google"` (auto-provisions organization and user on first login with `ADMIN` role).
  3. **Navigation Links**:
     - Button / Link: `"Already have an account? Log In"` → navigates to `/login`.

---

### PAGE 3: EXECUTIVE DASHBOARD (`/dashboard`)
- **Route**: `/dashboard` (Protected route).
- **Access Control**: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`. (Redirects or shows friendly message for `DEVELOPER`).
- **Core Features**:
  1. **Header & Polling Controls**:
     - Page Title & Subtitle.
     - Live Polling Toggle Switch (Enable/Disable auto-refresh every 5 seconds).
     - Manual `"Refresh Data"` Button.
     - Timezone Scope Badge: Displays `"Scored for UTC Day (resets at 00:00 UTC)"`.
  2. **Top Aggregate Statistics Cards** (`GET /api/v1/dashboard/stats`):
     - **Card 1: Total Guarded Requests Today**:
       - Primary count (`requests_today`).
       - Breakdown badges: Allowed count (Green), Blocked count (Red), Pending count (Yellow).
     - **Card 2: Total Spend Today**:
       - Monetary formatted amount (`total_spend_today` in `$USD`).
       - Organization-wide daily spend tracker.
     - **Card 3: Active AI Agents**:
       - Count of active registered agents (`total_agents`).
       - Quick link to `/agents`.
     - **Card 4: Registered Tools**:
       - Count of active tools (`total_tools`).
       - Quick link to `/tools`.
     - **Card 5: Pending Human Approvals**:
       - Count of currently pending reviews (`pending_today`).
       - Quick link to `/approvals` with alert indicator if > 0.
  3. **Agent Budget Utilization List / Progress Cards**:
     - Derived from `budget_utilization` array in `/dashboard/stats`.
     - Displays list/grid of agents with:
       - Agent Name.
       - Current Spend ($) vs Daily Budget Cap ($).
       - Visual Utilization Progress Bar (Color changes to yellow at 75%, red at 90%+).
       - Cap status (e.g. `"$14.20 / $50.00"` or `"$3.10 / Unlimited"`).
  4. **Live Activity Feed Table** (`GET /api/v1/dashboard/activity?limit=50&offset=0`):
     - Reverse-chronological table of all tool requests evaluated by the engine.
     - Table Columns:
       - `Timestamp` (Relative time e.g., "5s ago", with full UTC datetime on tooltip).
       - `Agent Name` (Badge with link to agent).
       - `Tool Name` (Monospace text badge).
       - `Decision` (Distinct color badge: `ALLOW` in Green, `DENY` in Red, `PENDING` in Yellow).
       - `Reason / Check Failure` (Descriptive explanation of policy, rate limit, or budget outcome).
       - `Latency` (Formatted in milliseconds e.g. `2.4 ms`).
       - `Request ID` (Monospace truncated UUID with one-click copy button).
     - Pagination Controls: `"Previous Page"`, `"Next Page"`, `"Page Size"` selector (10, 25, 50, 100).
     - Empty State: Informative illustration and text when no requests have been logged today.

---

### PAGE 4: AGENT MANAGEMENT & KILL SWITCH (`/agents`)
- **Route**: `/agents` (Protected route).
- **Access Control**: Read: All Roles. Create: `ADMIN`, `SECURITY`, `DEVELOPER`. Update/Delete: `ADMIN`, `SECURITY`.
- **Core Features**:
  1. **Top Actions Bar**:
     - Search input: Filter agents by name or description in real-time.
     - Status filter dropdown: All, `ACTIVE`, `INACTIVE`, `SUSPENDED`.
     - Primary Button: `"+ Create Agent"` (Visible to `ADMIN`, `SECURITY`, `DEVELOPER`).
  2. **Create Agent Modal / Dialog**:
     - Form Fields:
       - `Agent Name` (required, unique text, e.g., `FinanceBot`).
       - `Description` (optional text area, e.g., `Handles customer refunds and invoice processing`).
       - `Initial Status` (dropdown: `ACTIVE`, `INACTIVE`, `SUSPENDED`).
     - Actions: `"Cancel"` and `"Create Agent"` buttons.
     - API Call: `POST /api/v1/agents`
       - Request: `{"name": "...", "description": "...", "status": "ACTIVE"}`
       - Response (201 Created): Contains `id`, `name`, `status`, `api_key` (raw plaintext), `api_key_prefix`.
  3. **CRITICAL ONE-TIME API KEY REVEAL MODAL**:
     - When an agent is created, the backend returns the raw API key **EXACTLY ONCE**.
     - Modal presents:
       - Warning Banner: *"Save this API Key now. For security reasons, it will never be displayed again."*
       - Plaintext API Key box (e.g. `ag_agent_9f8e7d6c...`) with a prominent `"Copy to Clipboard"` button.
       - Agent UUID box with `"Copy UUID"` button.
       - Quick code snippet example showing how to initialize the Python SDK with this key.
       - `"I Have Securely Saved This Key"` confirmation button to close.
  4. **Agent List Table / Card Grid** (`GET /api/v1/agents`):
     - Columns / Details:
       - `Agent Name` (Bold).
       - `Agent ID (UUID)` (Click to copy).
       - `Description`.
       - `Status Badge`:
         - `ACTIVE` (Green)
         - `INACTIVE` (Slate/Gray)
         - `SUSPENDED` (Red - Emergency halted)
       - `Created Date` / `Last Updated`.
       - `Actions Menu / Buttons`:
         - **Emergency Kill-Switch Button / Toggle**:
           - One-click toggle between `ACTIVE` and `SUSPENDED`.
           - Instant confirmation modal: *"Suspending this agent will immediately reject all its tool calls at the gateway."*
           - Calls `PATCH /api/v1/agents/{agent_id}` with `{"status": "SUSPENDED"}`.
         - **Edit Agent Button**:
           - Opens modal to update `name`, `description`, or `status`.
           - Calls `PATCH /api/v1/agents/{agent_id}`.
         - **Soft Delete Button**:
           - Opens danger confirmation modal: *"Soft-deleting this agent will disable it while preserving audit logs."*
           - Calls `DELETE /api/v1/agents/{agent_id}` (204 No Content).
         - **View Permissions Link**: Navigates to `/permissions` filtered by this agent.
         - **Configure Budget Link**: Navigates to `/budgets` for this agent.

---

### PAGE 5: TOOLS REGISTRY & RISK TIERS (`/tools`)
- **Route**: `/tools` (Protected route).
- **Access Control**: Read: All Roles. Create: `ADMIN`, `SECURITY`, `DEVELOPER`. Update/Retire: `ADMIN`, `SECURITY`.
- **Core Features**:
  1. **Top Actions & Filters**:
     - Search input (filter by tool name or description).
     - Risk level filter: All, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
     - Status filter: All, `Active`, `Retired (Inactive)`.
     - Primary Button: `"+ Register New Tool"` (Visible to `ADMIN`, `SECURITY`, `DEVELOPER`).
  2. **Register Tool Modal / Dialog**:
     - Form Fields:
       - `Tool Name` (required string, e.g., `process_refund`, `query_database`, `delete_table`).
       - `Description` (detailed description of tool function and impact).
       - `Risk Level` Dropdown with Explanatory Badges:
         - `LOW` → Safe / Read-only actions (Allowed automatically).
         - `MEDIUM` → Standard operational actions (Allowed automatically).
         - `HIGH` → Financial / Sensitive actions (**Requires Human Manager Approval / HITL**).
         - `CRITICAL` → Destructive / Dangerous actions (**Always blocked by policy**).
       - `Is Active` (Checkbox / Toggle, defaults to true).
     - Actions: `"Cancel"` and `"Save Tool"` buttons.
     - API Call: `POST /api/v1/tools`
  3. **Tools Table / List** (`GET /api/v1/tools`):
     - Columns:
       - `Tool Name` (Monospace font).
       - `Description`.
       - `Risk Tier Badge` (Color-coded: LOW=Blue, MEDIUM=Yellow, HIGH=Orange, CRITICAL=Red).
       - `Status` (Active vs Retired/Inactive).
       - `Registered Date`.
       - `Action Buttons`:
         - **Edit Tool**: Opens modal to modify description, risk level, or active status (`PATCH /api/v1/tools/{tool_id}`).
         - **Retire / Deactivate Tool**: Toggle `is_active` to false (tools are soft-retired to maintain historical audit integrity; no hard delete).
         - **Permission Grants Count**: Shows how many agents are authorized to use this tool.

---

### PAGE 6: PERMISSIONS MATRIX (`/permissions`)
- **Route**: `/permissions` (Protected route).
- **Access Control**: Read: All Roles. Grant/Revoke: `ADMIN`, `SECURITY`.
- **Core Features**:
  1. **Dual Views**:
     - **View Option A: Visual Matrix Grid**:
       - Interactive 2D Grid: Rows = AI Agents, Columns = Tools.
       - Each intersection displays a clickable toggle or status badge:
         - Green Checkmark = `Allowed`
         - Red Cross / Gray = `Revoked / No Permission`
       - Clicking an intersection cell:
         - If granted → Prompts to revoke (`DELETE /api/v1/permissions/{agent_id}/{tool_id}`).
         - If not granted → Grants permission (`POST /api/v1/permissions` with `{"agent_id": "...", "tool_id": "...", "is_allowed": true}`).
     - **View Option B: Tabular List & Grant Drawer**:
       - Shows list of all granted permission records (`GET /api/v1/permissions`).
       - Columns: Agent Name, Tool Name, Status (`Allowed`), Granted Date, Revoke Action Button.
       - Filter by Agent Dropdown or Tool Dropdown.
  2. **Grant Permission Dialog**:
     - Button: `"+ Grant Permission"`
     - Form:
       - Select Agent (Dropdown of active agents).
       - Select Tool (Dropdown of active tools).
       - Permission State: `Allowed (True)` or `Denied (False)`.
     - API Call: `POST /api/v1/permissions` (Idempotent upsert).
  3. **Revoke Confirmation Modal**:
     - Confirms revoking access for a specific agent from executing the specified tool.
     - API Call: `DELETE /api/v1/permissions/{agent_id}/{tool_id}`.

---

### PAGE 7: POLICY ENGINE CONFIGURATION (`/policies`)
- **Route**: `/policies` (Protected route).
- **Access Control**: Read: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`. Write: `ADMIN`, `SECURITY`.
- **Core Features**:
  1. **Top Actions & Explanations**:
     - Header explaining that policies enforce the deterministic 11-step governance pipeline.
     - Primary Button: `"+ Create Policy"` (Visible to `ADMIN`, `SECURITY`).
  2. **Create / Edit Policy Modal**:
     - Form Fields:
       - `Policy Name` (required, e.g., `Production SQL Injection Defense`).
       - `Description` (optional, e.g., `Blocks destructive database commands across all tools`).
       - `Policy Type` (e.g., `PARAMETER_DENYLIST`, `RISK_OVERRIDE`, `ACTION_ALLOWLIST`).
       - `Active Status` (Toggle).
       - `Rules Configuration (Structured JSON / Visual Form)`:
         - Recognized keys validation (must include at least one of):
           - `allowed_actions`: Array of permitted action strings.
           - `blocked_actions`: Array of prohibited action strings.
           - `risk_thresholds`: Map of risk levels to outcomes (e.g. `{"LOW": "ALLOW", "HIGH": "HITL", "CRITICAL": "DENY"}`).
           - `max_cost_per_call`: Numeric dollar limit per individual invocation.
         - Includes pre-built quick-insert templates:
           - Template 1: *SQL Injection & Table Drop Guard*
           - Template 2: *OS Command Execution Guard (`rm -rf`, `chmod`)*
           - Template 3: *Financial Strict Approval Rules*
     - Client-side JSON schema validator to ensure no empty or malformed payload before submission.
     - Submit Action: `POST /api/v1/policies` (Create) or `PATCH /api/v1/policies/{policy_id}` (Update).
  3. **Policy List Cards / Table** (`GET /api/v1/policies`):
     - Displays policy cards showing:
       - Policy Name & Type.
       - Description.
       - Formatted Rules Code Block / Summary Chips.
       - Active Status Badge.
       - Created & Updated Timestamps.
       - Actions: Edit Policy, Toggle Active/Inactive, Soft-Delete (`DELETE /api/v1/policies/{policy_id}`).

---

### PAGE 8: BUDGETS & RATE LIMITS (`/budgets`)
- **Route**: `/budgets` (Protected route).
- **Access Control**: Read: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`. Edit: `ADMIN`, `SECURITY`.
- **Core Features**:
  1. **Budgets Table / Overview** (`GET /api/v1/budgets`):
     - Note: Budget rows are automatically provisioned when agents are created.
     - Table Columns:
       - `Agent Name` (Joined via agent_id).
       - `Today's Current Spend` ($USD formatted).
       - `Daily Budget Cap` ($USD or `"Unlimited"`).
       - `Session Budget Cap` ($USD or `"Unlimited"`).
       - `Rate Limit (Requests / Minute)` (e.g. `30 req/min` or `"Unlimited"`).
       - `Daily Request Cap` (e.g. `10,000 req/day` or `"Unlimited"`).
       - `Spend vs Cap Utilization Progress Bar`.
       - `Action Button`: `"Configure Caps"`.
  2. **Edit Budget Modal**:
     - Triggered by clicking `"Configure Caps"` for an agent.
     - Form Fields (all optional, empty = unlimited):
       - `Max Budget per Day ($)` (number input, e.g. `50.00`).
       - `Max Budget per Session ($)` (number input, e.g. `10.00`).
       - `Max Requests per Minute` (integer input, e.g. `60` - prevents infinite runaway loops).
       - `Max Requests per Day` (integer input, e.g. `5000`).
     - Helper text: *"Leave any field empty or blank to remove the cap (unlimited access)."*
     - Submit Action: `PATCH /api/v1/budgets/{budget_id}`
       - Payload: `{"max_budget_per_day": 50.0, "max_budget_per_session": 10.0, "max_requests_per_minute": 60, "max_requests_per_day": 5000}`
       - Success: Updates table, shows confirmation toast.

---

### PAGE 9: HUMAN-IN-THE-LOOP (HITL) APPROVALS QUEUE (`/approvals`)
- **Route**: `/approvals` (Protected route).
- **Access Control**: `ADMIN`, `MANAGER` only. (Displays access restricted banner for other roles).
- **Core Features**:
  1. **Queue Filter Tabs**:
     - `Pending Approvals` (Default tab with badge showing active count).
     - `Resolved: Approved`.
     - `Resolved: Denied`.
     - `Expired` (Requests older than 24 hours).
     - `All Records`.
  2. **Pending Approvals Feed & Review Drawer** (`GET /api/v1/hitl?status=PENDING`):
     - Each pending card displays:
       - Request ID & Created Timestamp.
       - Expiration Countdown Timer (e.g., `"Expires in 18h 32m"` based on `expires_at`).
       - Agent Name proposing the action.
       - Tool Name being called (e.g., `process_refund`).
       - Estimated Cost & Token count.
       - **Input Payload Inspector**: Expandable syntax-highlighted JSON viewer showing the full parameter payload proposed by the agent (e.g., `{"customer_id": "CUST-99", "amount": 500.0, "reason": "Customer cancellation"}`).
  3. **Interactive Review & Decision Actions**:
     - Reviewer Notes Input: Text area for manager explanation or audit comments (optional).
     - **Button 1: [ APPROVE & EXECUTE ]** (Green Primary):
       - Triggers `POST /api/v1/hitl/{hitl_id}/approve` with `{"review_notes": "..."}`.
       - Backend commits `HITL_APPROVED` audit log and safely resumes tool execution.
       - Shows execution outcome in real-time (`Executed successfully` or `Mock result`).
       - Removes item from pending queue and shows success banner.
     - **Button 2: [ DENY ACTION ]** (Red Danger):
       - Prompts for required denial reasoning.
       - Triggers `POST /api/v1/hitl/{hitl_id}/deny` with `{"review_notes": "..."}`.
       - Backend commits `HITL_DENIED` audit log and permanently halts tool execution.
       - Moves card to Denied tab.
  4. **Resolved History View**:
     - Shows who reviewed the item (`reviewer_id`), review timestamp (`reviewed_at`), reviewer notes, and resulting output payload (`output_payload`).

---

### PAGE 10: CRYPTOGRAPHIC AUDIT VAULT & CHAIN VERIFIER (`/audit`)
- **Route**: `/audit` (Protected route).
- **Access Control**: `ADMIN`, `AUDITOR` only. (Read-only immutable ledger for compliance officers).
- **Core Features**:
  1. **Top Cryptographic Verification Banner**:
     - Prominent Action Button: **"⚡ Verify Cryptographic Hash Chain"** (Primary Action).
     - Status Indicator Card:
       - Default state: *"Last verified: Not verified in this session"*
       - When clicked: Calls `POST /api/v1/audit/verify`.
       - **Verification Success State (`status: "VALID"`):**
         - Displays Big Green Badge: `CHAIN VALID & IMMUTABLE`.
         - Shows total records verified (e.g., `1,428 records verified`), verification duration (`14.2 ms`), and message: *"Zero tampering detected. All SHA-256 cryptographic hashes match sequence continuity."*
       - **Verification Failure State (`status: "INVALID"`):**
         - Displays Big Red Alert: `CHAIN COMPROMISED / TAMPER DETECTED`.
         - Identifies exact `broken_sequence_number` (e.g., `Sequence #412`), `broken_record_id`, error type (`HASH_MISMATCH` or `SEQUENCE_GAP`), and forensic details.
  2. **Audit Log Table** (`GET /api/v1/audit?limit=50&offset=0`):
     - Reverse-chronological table of all recorded governance decisions.
     - Table Columns:
       - `Seq #` (Sequence number e.g. `1042`).
       - `Timestamp` (UTC format).
       - `Event Type` (e.g. `TOOL_REQUEST_EVALUATED`, `HITL_APPROVED`, `HITL_DENIED`, `TOOL_EXECUTED`).
       - `Decision` (Color-coded: `ALLOW`, `DENY`, `PENDING`, `EXECUTED`).
       - `Current Hash` (Monospace truncated SHA-256 hash e.g. `e3b0c442...` with hover full hash & copy button).
       - `Previous Hash` (Monospace truncated SHA-256 hash linking to previous block).
       - `Payload Inspector Button`: Eye icon / `"Inspect Payload"`.
  3. **Audit Record Deep Inspection Modal / Drawer** (`GET /api/v1/audit/{audit_id}`):
     - Displays complete forensic record:
       - Full Sequence Number & Event ID.
       - Associated Agent ID & Tool ID.
       - Full Cryptographic Current Hash & Previous Hash.
       - Exact JSON Payload recorded at moment of decision.
       - 11-Step Policy Check breakdown results (Auth, Permission, Risk, Budget, Rate Limit, Parameter Sanitization).
       - One-click button to copy full JSON for compliance export.
  4. **Pagination Controls**: Limit and offset navigation for traversing historical records.

---

### PAGE 11: SETTINGS, API KEYS & PROFILE (`/settings`)
- **Route**: `/settings` (Protected route).
- **Access Control**: All authenticated users.
- **Core Features**:
  1. **User Profile Section** (`GET /api/v1/auth/me`):
     - User Full Name.
     - User Email Address.
     - Assigned Role Badge (with tooltip explaining role capabilities: Admin, Security, Auditor, Manager, Developer).
     - Account Status (Active).
  2. **Organization & Workspace Details**:
     - Organization Name.
     - Organization Slug (e.g. `acme-corp`).
     - Organization UUID.
     - Link / Instructions for team members to join using the organization slug.
  3. **Organization API Keys Management Section**:
     - Explanatory Header: *"API keys allow SDK clients and AI agents to authenticate with the AgentGuard pre-dispatch gateway."*
     - Button: `"+ Generate New API Key"` (Calls `POST /api/v1/auth/api-keys`).
       - Modal inputs: `Key Name` (e.g. `Production Agent Cluster`), `Optional Associated Agent`, `Optional Expiration Date`.
       - Shows raw API key once with copy button.
     - API Keys Table (`GET /api/v1/auth/api-keys`):
       - Name.
       - Key Prefix (e.g., `ag_live_4a8b...`).
       - Associated Agent (or Global).
       - Created Date & Expiration Date.
       - Status (Active vs Revoked).
       - Revoke Key Action Button (`DELETE /api/v1/auth/api-keys/{key_id}`).
  4. **System Environment & Backend Health**:
     - Displays backend status (Online / Healthy) by checking `/health` and `/ready`.
     - Displays API Base URL.
  5. **Session Actions**:
     - `"Log Out"` Button: Clears JWT token from browser storage, purges user state, and redirects to `/login`.

---

## 5. GLOBAL UI COMPONENTS & INTERACTIVE PATTERNS

1. **Top Navigation Bar**:
   - Organization Switcher / Workspace Name display.
   - Live System Status Pill (Green dot = Connected, Red dot = Backend unreachable).
   - Approvals Notification Bell (Shows badge with count of pending HITL reviews).
   - User Avatar with Dropdown: Full name, Role badge, Settings link, Log Out trigger.
2. **Left Sidebar Menu**:
   - Icons and labels for all 9 main pages.
   - Dynamic badge for `Approvals` showing count of pending items.
   - Collapse / Expand sidebar toggle for responsive layouts.
3. **Empty States & Loading Skeletons**:
   - Every table and card view must have an animated loading skeleton while waiting for API responses.
   - Clean, friendly empty states with a direct call-to-action button (e.g. *"No agents registered yet. Click '+ Create Agent' to register your first AI agent."*).
4. **Toast Notifications & Modal Confirmations**:
   - Floating toast messages for all asynchronous mutations (e.g., *"Agent created successfully"*, *"Permission granted"*, *"Budget caps updated"*, *"API Key copied to clipboard"*).
   - Destructive actions (Emergency Kill Switch, Revoke Key, Delete Agent, Deny HITL) must always trigger a confirmation modal before dispatching.
5. **JSON Payloads & Hash Viewers**:
   - Monospace font for UUIDs, SHA-256 hashes, API keys, and parameter payloads.
   - One-click copy buttons with temporary checkmark feedback on all identifiers.

---

## 6. COMPLETE API ENDPOINTS REFERENCE TABLE

| HTTP Method | Endpoint Path | Description | Required Role |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register user & provision org | Public |
| `POST` | `/api/v1/auth/login` | Authenticate & get JWT token | Public |
| `GET` | `/api/v1/auth/google/login` | Initiate Google OAuth redirect | Public |
| `POST` | `/api/v1/auth/google/exchange` | Exchange OAuth code for JWT | Public |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | Any Authenticated |
| `POST` | `/api/v1/auth/api-keys` | Generate new API key | ADMIN, SECURITY, DEVELOPER |
| `GET` | `/api/v1/auth/api-keys` | List active organization API keys | Any Authenticated |
| `DELETE` | `/api/v1/auth/api-keys/{key_id}` | Revoke an API key | ADMIN, SECURITY, DEVELOPER |
| `GET` | `/api/v1/dashboard/stats` | Fetch aggregate counts & spend today | ADMIN, SECURITY, AUDITOR, MANAGER |
| `GET` | `/api/v1/dashboard/activity` | Paginated live activity feed | ADMIN, SECURITY, AUDITOR, MANAGER |
| `POST` | `/api/v1/agents` | Register agent & provision API key | ADMIN, SECURITY, DEVELOPER |
| `GET` | `/api/v1/agents` | List active organization agents | Any Authenticated |
| `GET` | `/api/v1/agents/{agent_id}` | Get agent details by UUID | Any Authenticated |
| `PATCH` | `/api/v1/agents/{agent_id}` | Update agent metadata or kill-switch | ADMIN, SECURITY |
| `DELETE` | `/api/v1/agents/{agent_id}` | Soft-delete agent | ADMIN, SECURITY |
| `POST` | `/api/v1/tools` | Register new tool with risk level | ADMIN, SECURITY, DEVELOPER |
| `GET` | `/api/v1/tools` | List all organization tools | Any Authenticated |
| `GET` | `/api/v1/tools/{tool_id}` | Get tool details by UUID | Any Authenticated |
| `PATCH` | `/api/v1/tools/{tool_id}` | Update tool risk or retire status | ADMIN, SECURITY |
| `POST` | `/api/v1/permissions` | Grant/update tool permission (upsert)| ADMIN, SECURITY |
| `DELETE` | `/api/v1/permissions/{agent_id}/{tool_id}` | Revoke tool permission | ADMIN, SECURITY |
| `GET` | `/api/v1/permissions` | List all permission grants | Any Authenticated |
| `GET` | `/api/v1/permissions/agents/{agent_id}` | List permissions for agent | Any Authenticated |
| `GET` | `/api/v1/permissions/tools/{tool_id}` | List permissions for tool | Any Authenticated |
| `GET` | `/api/v1/policies` | List all governance policies | ADMIN, SECURITY, AUDITOR, MANAGER |
| `POST` | `/api/v1/policies` | Create new governance policy | ADMIN, SECURITY |
| `PATCH` | `/api/v1/policies/{policy_id}` | Update policy rules / status | ADMIN, SECURITY |
| `DELETE` | `/api/v1/policies/{policy_id}` | Soft-delete policy | ADMIN, SECURITY |
| `GET` | `/api/v1/budgets` | List all agent budgets and spend | ADMIN, SECURITY, AUDITOR, MANAGER |
| `GET` | `/api/v1/budgets/{budget_id}` | Get single budget by ID | ADMIN, SECURITY, AUDITOR, MANAGER |
| `PATCH` | `/api/v1/budgets/{budget_id}` | Update budget caps & rate limits | ADMIN, SECURITY |
| `GET` | `/api/v1/hitl` | List pending/resolved approvals | ADMIN, MANAGER |
| `GET` | `/api/v1/hitl/{hitl_id}` | Get approval request details | ADMIN, MANAGER |
| `POST` | `/api/v1/hitl/{hitl_id}/approve` | Approve request & resume execution | ADMIN, MANAGER |
| `POST` | `/api/v1/hitl/{hitl_id}/deny` | Deny request & block execution | ADMIN, MANAGER |
| `GET` | `/api/v1/audit` | Paginated reverse-chronological logs | ADMIN, AUDITOR |
| `GET` | `/api/v1/audit/{audit_id}` | Get single audit log & checks | ADMIN, AUDITOR |
| `POST` | `/api/v1/audit/verify` | Cryptographically verify hash chain | ADMIN, AUDITOR |
| `GET` | `/health` | System health check | Public |
| `GET` | `/ready` | System readiness check | Public |

---

## 7. STEP-BY-STEP USER JOURNEY & VERIFICATION FLOW

When building and testing the frontend website, ensure this exact user journey works end-to-end:
1. **User Sign Up / Login**: User registers with email & password or clicks **"Continue with Google"** → receives JWT token → bootstraps session via `/auth/me`.
2. **Dashboard Overview**: User lands on `/dashboard` → views live statistics (requests today, allowed/blocked/pending, total spend, active agents, live activity feed).
3. **Register Agent**: User navigates to `/agents` → clicks `+ Create Agent` → receives one-time raw API key dialog → copies key and agent UUID.
4. **Register Tools**: User navigates to `/tools` → registers tools (e.g. `read_customer` with `LOW` risk, `process_refund` with `HIGH` risk, `delete_database` with `CRITICAL` risk).
5. **Assign Permissions**: User navigates to `/permissions` → grants permissions for the agent to use `read_customer` and `process_refund`.
6. **Set Budgets & Rate Limits**: User navigates to `/budgets` → configures `$50/day` budget and `30 req/min` rate limit on the agent.
7. **Configure Policies**: User navigates to `/policies` → creates parameter denylist rules for SQL injection defense.
8. **Human-in-the-Loop Review**: When a high-risk tool call is submitted by an agent, it appears under `/approvals` as `PENDING` → Manager inspects payload parameters and clicks **[ APPROVE ]** with reviewer notes.
9. **Verify Cryptographic Audit Vault**: Auditor navigates to `/audit` → views chronological immutable ledger with previous & current SHA-256 hashes → clicks **"Verify Cryptographic Hash Chain"** → receives instant `CHAIN VALID` confirmation.
10. **Emergency Kill-Switch**: Admin visits `/agents` → clicks toggle to switch agent status to `SUSPENDED` → agent is immediately blocked from all future tool calls.
11. **Profile & Log Out**: User visits `/settings` → inspects organization info, creates secondary API keys, and clicks **"Log Out"** to end session.
