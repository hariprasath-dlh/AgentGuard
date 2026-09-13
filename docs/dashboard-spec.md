# AgentGuard Control Plane Dashboard Specification

> **Single Source of Truth Reference**: `project.md` (Phases 1–13).  
> **Target Consumer**: Lovable AI (or frontend engineer) exporting code to `frontend/`.  
> **Companion File**: [`docs/openapi.json`](file:///d:/agentguard/docs/openapi.json) (exact OpenAPI 3.1 schema exported directly from FastAPI).

---

## 1. System Overview & Aesthetic Guidance

AgentGuard is a pre-dispatch security and governance control plane for autonomous AI agents. The Control Plane Dashboard is the visual "Control Room" for human administrators, security officers, auditors, and engineering managers.

### Tone & Visual Identity
- **Vibe**: Mission-critical cyber-defense control room. High-contrast dark theme (slate/zinc/neutral backgrounds), crisp typography (Inter, JetBrains Mono for hashes/keys/IDs), clean status indicators.
- **Not a generic student CRUD app**: No playful pastels or casual elements. Use clean status badges:
  - `ALLOW` / `VALID` / `ACTIVE`: Emerald / Green (`#10B981`)
  - `PENDING`: Amber / Warning (`#F59E0B`)
  - `DENY` / `INVALID` / `CRITICAL` / `DELETED`: Crimson / Red (`#EF4444`)
  - Risk Badges: `LOW` (slate/blue), `MEDIUM` (amber), `HIGH` (orange), `CRITICAL` (red-violet).
- **Latency & Timestamps**: Show relative time with tooltip full UTC timestamp (e.g. `2m ago` -> `2026-09-06 09:40:00 UTC`).

---

## 2. Global Architecture & Networking

- **Tech Stack**: Next.js (App Router), React, TypeScript, Tailwind CSS.
- **Backend Base URL**: Configured via environment variable `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`).
- **Endpoint Prefix**: All resource endpoints are prefixed with `/api/v1`.
- **System Endpoints**:
  - `GET /health` -> `{"status": "healthy"}`
  - `GET /ready` -> `{"status": "ready"}`
- **Authentication Header**: Every authenticated request must send:
  ```http
  Authorization: Bearer <jwt_access_token>
  Content-Type: application/json
  ```
- **Tenant Scoping**: All backend queries are strictly scoped to the caller's `organization_id` extracted from the JWT token. The frontend never needs to pass `organization_id` in path or query parameters.

---

## 3. Authentication & Session Lifecycle

### 3.1 Login (`POST /api/v1/auth/login`)
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword",
    "organization_slug": "optional-org-slug"
  }
  ```
- **Response** (`TokenResponse`):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer",
    "expires_in": 3600
  }
  ```
- **Storage**: Store `access_token` in memory or `localStorage`.
- **Session Profile Bootstrapping**: Immediately after receiving the token, call `GET /api/v1/auth/me`.
  ```json
  {
    "id": "uuid",
    "organization_id": "uuid",
    "role": "ADMIN",
    "email": "user@example.com",
    "full_name": "Alice Admin",
    "is_active": true
  }
  ```
  The returned `role` controls all UI visibility and access gating.

### 3.2 Registration (`POST /api/v1/auth/register`)
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword",
    "full_name": "Alice Admin",
    "organization_name": "Acme Corp",
    "organization_slug": "acme-corp",
    "role": "ADMIN"
  }
  ```
- **Response** (`UserResponse`): 201 Created.

### 3.3 Token Expiration Policy (CRITICAL)
- The backend uses static JWT tokens with fixed expiration (`ACCESS_TOKEN_EXPIRE_MINUTES = 60`).
- **NO REFRESH TOKENS EXIST**: The backend does not implement `/auth/refresh` or refresh cookie rotation.
- **Frontend Behavior**: When any API call receives HTTP `401 Unauthorized`:
  1. Clear the stored token and user session.
  2. Immediately redirect to `/login` with an informational banner: `"Your session has expired. Please log in again."`
  3. Do NOT attempt background refresh or retry loops.

---

## 4. Role-Based Access Control (RBAC) Matrix

The backend enforces five distinct roles. The frontend UI must hide or disable actions that the user's role cannot execute.

| Feature / Action | Required Backend Roles | UI Behavior if Unauthorized |
|---|---|---|
| **View Dashboard (Stats & Activity)** | `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` | Developer: redirect to Agents or show restricted banner |
| **View Agents / Tools / Permissions** | All 5 Roles (`ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`, `DEVELOPER`) | Visible to all |
| **Create Agent / Tool** | `ADMIN`, `SECURITY`, `DEVELOPER` | Hide "+ Register" button for Auditor/Manager |
| **Edit / Deactivate Agent or Tool** | `ADMIN`, `SECURITY` | Disable edit controls for Developer/Manager/Auditor |
| **Grant / Revoke Permissions** | `ADMIN`, `SECURITY` | Read-only matrix for Developer/Manager/Auditor |
| **View Policies** | `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` | Hidden from Developer |
| **Create / Edit / Delete Policies** | `ADMIN`, `SECURITY` | Hide "+ New Policy" / edit buttons for Auditor/Manager |
| **View Budgets** | `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` | Hidden from Developer |
| **Edit Budgets (PATCH)** | `ADMIN`, `SECURITY` | Hide edit sliders/inputs for Auditor/Manager |
| **View Approvals (HITL)** | `ADMIN`, `MANAGER` | Hidden from Security/Auditor/Developer |
| **Approve / Deny HITL Request** | `ADMIN`, `MANAGER` | Action buttons only for Admin/Manager |
| **View Audit Vault** | `ADMIN`, `AUDITOR` | Hidden from Security/Manager/Developer |
| **Trigger Hash Chain Verification** | `ADMIN`, `AUDITOR` | Button only for Admin/Auditor |
| **Manage API Keys (Settings)** | Authenticated User (`ADMIN`, `SECURITY`, etc.) | Org-scoped |

---

## 5. Real-Time Activity Feed & Polling Strategy

- **Constraint**: WebSockets and Server-Sent Events (SSE) are **strictly out of scope** for this phase per `project.md`.
- **Implementation**: The dashboard feed must use **HTTP Polling**:
  - Polling Endpoint: `GET /api/v1/dashboard/activity?limit=25&offset=0`
  - Polling Frequency: Every **5 seconds** when the browser tab is active/visible.
  - Idle Optimization: Pause polling when the document is hidden (`document.hidden`).
  - Merge Strategy: Prepend newer items based on `request_id` or timestamp to avoid jarring page jumps.

---

## 6. Detailed Screen Specifications

### Screen 1: Dashboard (Home Overview)
- **Route**: `/` or `/dashboard`
- **RBAC**: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` can view.
- **Data Displayed**:
  1. **Top Metric Cards** (sourced from `GET /api/v1/dashboard/stats`):
     - Total Agents (`total_agents`)
     - Total Tools (`total_tools`)
     - Requests Today (`requests_today`) — resets at UTC midnight (00:00:00 UTC)
     - Decisions Breakdown: Allowed (`allowed_today`), Blocked (`blocked_today`), Pending Review (`pending_today`)
     - Total Spend Today (`total_spend_today` formatted as `$0.00`)
  2. **Budget Utilization Bar/Chart** (from `stats.budget_utilization`):
     - Shows list of agents with `current_spend` vs `max_budget_per_day` (percentage progress bar).
  3. **Live Activity Feed** (sourced from `GET /api/v1/dashboard/activity?limit=20`):
     - Table / Stream with columns: Timestamp, Agent Name (`agent_name`), Tool Name (`tool_name`), Decision badge (`ALLOW`, `DENY`, `PENDING`), Reason (`reason`), Execution Latency (`latency_ms` formatted e.g. `24ms`).
- **Endpoints Called**:
  - `GET /api/v1/dashboard/stats`
  - `GET /api/v1/dashboard/activity?limit=20&offset=0` (polled every 5–10s)
- **User Actions**:
  - Filter activity feed by decision (`ALL`, `ALLOW`, `DENY`, `PENDING`).
  - Click row in activity feed to expand details (reason, request ID, agent ID).
  - Quick action: "Go to Approvals" badge if `pending_today > 0`.

---

### Screen 2: Agents
- **Route**: `/agents`
- **RBAC**: Read: all roles. Create: `ADMIN`, `SECURITY`, `DEVELOPER`. Mutate/Delete: `ADMIN`, `SECURITY`.
- **Data Displayed**:
  - Table of registered agents: Name (`name`), Description (`description`), Status (`ACTIVE`, `INACTIVE`, `SUSPENDED`, `DELETED`), Created At.
  - Spend & Budget: Daily spend and cap.
- **Endpoints Called**:
  - `GET /api/v1/agents`
  - `GET /api/v1/budgets` (for spend/cap data)
  - `POST /api/v1/agents` (Modal: name, description, status)
  - `PATCH /api/v1/agents/{id}` (Edit name, description, status)
  - `DELETE /api/v1/agents/{id}` (Soft-delete -> sets status to `DELETED`)
- **API Architectural Note (Client-Side Joining Required)**:
  - `GET /api/v1/agents` returns only agent metadata (`id`, `name`, `description`, `status`). It does NOT contain budget caps or spend.
  - To show budget data on the agent table, the frontend must make two calls: `GET /api/v1/agents` and `GET /api/v1/budgets`, joining them in-memory using `budget.agent_id == agent.id`.
  - Note: `Agent` model in the backend does not have an `environment` column (e.g., `prod`/`staging`). Do not display an environment filter or column unless populated by client-side tags.
- **One-Time Key Warning on Create**:
  - When `POST /api/v1/agents` succeeds, the response returns `api_key: "ag_agent_..."`.
  - The UI **must** display a modal with a copy button and a prominent warning: *"This API key will never be shown again. Copy and store it in your agent's environment variables now."*

---

### Screen 3: Tools & Permissions
- **Route**: `/tools`
- **RBAC**:
  - View: All 5 roles.
  - Create Tool: `ADMIN`, `SECURITY`, `DEVELOPER`.
  - Update Tool: `ADMIN`, `SECURITY`.
  - Grant/Revoke Permission: `ADMIN`, `SECURITY`.
- **Data Displayed**:
  - List / Grid of Tools: Tool Name (`name`), Description (`description`), Risk Level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), Active Status toggle (`is_active`).
  - Permissions Drawer / Matrix: For each tool or agent, display whether permission is granted (`is_allowed`).
- **Endpoints Called**:
  - `GET /api/v1/tools`
  - `GET /api/v1/permissions`
  - `POST /api/v1/tools` (Create tool)
  - `PATCH /api/v1/tools/{id}` (Update name, description, risk_level, is_active)
  - `POST /api/v1/permissions` (Grant/upsert permission: `{ "agent_id": "...", "tool_id": "...", "is_allowed": true }`)
  - `DELETE /api/v1/permissions/{agent_id}/{tool_id}` (Revoke permission)
- **API Architectural Note (Client-Side Joining Required)**:
  - `GET /api/v1/tools` does not embed permitted agents.
  - To render the matrix or permitted agents per tool, the frontend must fetch `GET /api/v1/tools`, `GET /api/v1/agents`, and `GET /api/v1/permissions`, and join `agent_tool_permissions` on `(tool_id, agent_id)`.
  - Tools cannot be hard deleted (no `DELETE /tools/{id}` endpoint exists to preserve audit trail integrity); tools are retired by setting `is_active: false` via `PATCH`.

---

### Screen 4: Policies
- **Route**: `/policies`
- **RBAC**: Read: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`. Write: `ADMIN`, `SECURITY`.
- **Data Displayed**:
  - Policy card/table: Name (`name`), Type (`policy_type`, e.g., `RISK`, `PARAM_DENYLIST`, `ACTION_RULES`), Rules summary, Active Status (`is_active`).
- **Endpoints Called**:
  - `GET /api/v1/policies`
  - `POST /api/v1/policies`
  - `PATCH /api/v1/policies/{id}`
  - `DELETE /api/v1/policies/{id}` (Soft-delete -> sets `is_active: false`)
- **Rules Validation Contract**:
  - When creating or editing a policy, the `rules` JSON object **must** contain at least one of these top-level keys:
    - `"allowed_actions"`: `["read", "query"]`
    - `"blocked_actions"`: `["drop", "delete"]`
    - `"risk_thresholds"`: `{"LOW": "ALLOW", "MEDIUM": "ALLOW", "HIGH": "HITL", "CRITICAL": "DENY"}`
    - `"max_cost_per_call"`: `10.0`
  - The UI should provide a structured form/editor that guarantees this schema, avoiding raw invalid JSON submissions that result in HTTP 422.

---

### Screen 5: Budgets
- **Route**: `/budgets`
- **RBAC**: Read: `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER`. Edit: `ADMIN`, `SECURITY`.
- **Data Displayed**:
  - Table of agent budgets:
    - Agent Name (joined from `GET /api/v1/agents`)
    - Max Requests per Minute (`max_requests_per_minute` or "Unlimited")
    - Max Requests per Day (`max_requests_per_day` or "Unlimited")
    - Session Cost Cap (`max_budget_per_session` or "Unlimited")
    - Daily Cost Cap (`max_budget_per_day` or "Unlimited")
    - Current Spend (`current_spend` formatted as `$X.XX`)
- **Endpoints Called**:
  - `GET /api/v1/budgets`
  - `GET /api/v1/agents` (to map `agent_id` to human-readable `agent_name`)
  - `PATCH /api/v1/budgets/{id}`:
    ```json
    {
      "max_requests_per_minute": 60,
      "max_requests_per_day": 5000,
      "max_budget_per_session": 10.0,
      "max_budget_per_day": 50.0
    }
    ```
- **User Actions**:
  - "Edit Caps" modal: Allows modifying numbers or clearing them to set back to `null` (unlimited).

---

### Screen 6: Approvals (Human-in-the-Loop Queue)
- **Route**: `/approvals`
- **RBAC**: Restricted to `ADMIN` and `MANAGER`. Other roles receive 403.
- **Data Displayed**:
  - Pending Approval Cards/Rows:
    - Tool Name (`tool_name`)
    - Agent ID / Agent Name (`agent_id`)
    - Requested Action & Parameters (formatted JSON viewer of `input_payload`)
    - Expiration countdown (`expires_at`)
    - Created At
  - History Tab: Filter by `status` (`APPROVED`, `DENIED`, `EXPIRED`).
- **Endpoints Called**:
  - `GET /api/v1/hitl?status=PENDING` (Polled or refreshed)
  - `GET /api/v1/hitl?status=APPROVED` / `DENIED` / `EXPIRED` (for history tab)
  - `POST /api/v1/hitl/{id}/approve`:
    ```json
    {
      "review_notes": "Approved for customer #1234"
    }
    ```
  - `POST /api/v1/hitl/{id}/deny`:
    ```json
    {
      "review_notes": "Suspected hallucination or budget exceedance"
    }
    ```
- **UI Safety & State Invariants**:
  - After clicking Approve or Deny, disable buttons immediately to prevent double submissions.
  - If a request expires while on-screen (`expires_at < now`), disable action buttons and badge as `EXPIRED`.

---

### Screen 7: Audit Vault
- **Route**: `/audit`
- **RBAC**: Restricted to `ADMIN` and `AUDITOR`. Other roles receive 403.
- **Data Displayed**:
  - **Cryptographic Status Banner**:
    - "Verify Hash Chain" button.
    - When verified, displays large status badge:
      - `CHAIN VALID` (Emerald badge): All records intact, verified from sequence 1. Total records and verification time (`duration_ms`).
      - `CHAIN INVALID` (Red alert banner): Displays sequence number and `broken_record_id`, error type (`HASH_MISMATCH`, `SEQUENCE_GAP_OR_OUT_OF_ORDER`), and tamper details.
  - **Audit Records Table** (`GET /api/v1/audit?limit=50&offset=0`):
    - Sequence # (`sequence_number`)
    - Timestamp (`created_at`)
    - Event Type (`event_type`: `TOOL_REQUEST_EVALUATED`, `HITL_APPROVED`, `TOOL_EXECUTED`, etc.)
    - Decision (`ALLOW`, `DENY`, `PENDING`)
    - Current SHA-256 Hash (`current_hash` truncated with click-to-copy)
    - Previous Hash (`previous_hash` truncated)
    - Expandable Drawer: Full event payload (`payload`), parameters, policy check evaluations.
- **Endpoints Called**:
  - `GET /api/v1/audit?limit=50&offset=0` (Paginated)
  - `GET /api/v1/audit/{id}` (Details)
  - `POST /api/v1/audit/verify` (Verification trigger)

---

### Screen 8: Settings (Organization & API Keys)
- **Route**: `/settings`
- **RBAC**: Authenticated users.
- **Scope Resolution**: `project.md` mentions "Settings screens". The backend provides organization metadata via `/auth/me` and dedicated API key management endpoints on `/auth/api-keys`.
- **Data Displayed**:
  1. **Organization Profile**:
     - Organization Name, Slug, Organization ID.
     - Current User Profile: Name, Email, Assigned Role (`role`).
  2. **Agent & Service API Keys Management**:
     - Active API Keys Table: Key Name (`name`), Key Prefix (`key_prefix`, e.g. `ag_agent_...`), Bound Agent (`agent_id`), Created At, Expires At.
     - Action: Revoke Key (`DELETE /api/v1/auth/api-keys/{id}`).
     - Action: Generate Manual API Key (`POST /api/v1/auth/api-keys`).
- **Endpoints Called**:
  - `GET /api/v1/auth/me`
  - `GET /api/v1/auth/api-keys`
  - `POST /api/v1/auth/api-keys`
  - `DELETE /api/v1/auth/api-keys/{id}`

---

## 7. Endpoint Summary Table

| Screen | Method | Exact Backend Endpoint Path | Auth Required | Minimum Role |
|---|---|---|---|---|
| **Auth** | `POST` | `/api/v1/auth/login` | No | Public |
| **Auth** | `POST` | `/api/v1/auth/register` | No | Public |
| **Global** | `GET` | `/api/v1/auth/me` | Bearer JWT | All |
| **Dashboard** | `GET` | `/api/v1/dashboard/stats` | Bearer JWT | `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` |
| **Dashboard** | `GET` | `/api/v1/dashboard/activity` | Bearer JWT | `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` |
| **Agents** | `GET` | `/api/v1/agents` | Bearer JWT | All |
| **Agents** | `POST` | `/api/v1/agents` | Bearer JWT | `ADMIN`, `SECURITY`, `DEVELOPER` |
| **Agents** | `GET` | `/api/v1/agents/{id}` | Bearer JWT | All |
| **Agents** | `PATCH` | `/api/v1/agents/{id}` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Agents** | `DELETE` | `/api/v1/agents/{id}` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Tools** | `GET` | `/api/v1/tools` | Bearer JWT | All |
| **Tools** | `POST` | `/api/v1/tools` | Bearer JWT | `ADMIN`, `SECURITY`, `DEVELOPER` |
| **Tools** | `PATCH` | `/api/v1/tools/{id}` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Permissions** | `GET` | `/api/v1/permissions` | Bearer JWT | All |
| **Permissions** | `POST` | `/api/v1/permissions` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Permissions** | `DELETE`| `/api/v1/permissions/{agent_id}/{tool_id}` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Policies** | `GET` | `/api/v1/policies` | Bearer JWT | `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` |
| **Policies** | `POST` | `/api/v1/policies` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Policies** | `PATCH` | `/api/v1/policies/{id}` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Policies** | `DELETE`| `/api/v1/policies/{id}` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Budgets** | `GET` | `/api/v1/budgets` | Bearer JWT | `ADMIN`, `SECURITY`, `AUDITOR`, `MANAGER` |
| **Budgets** | `PATCH` | `/api/v1/budgets/{id}` | Bearer JWT | `ADMIN`, `SECURITY` |
| **Approvals** | `GET` | `/api/v1/hitl` | Bearer JWT | `ADMIN`, `MANAGER` |
| **Approvals** | `POST` | `/api/v1/hitl/{id}/approve` | Bearer JWT | `ADMIN`, `MANAGER` |
| **Approvals** | `POST` | `/api/v1/hitl/{id}/deny` | Bearer JWT | `ADMIN`, `MANAGER` |
| **Audit Vault**| `GET` | `/api/v1/audit` | Bearer JWT | `ADMIN`, `AUDITOR` |
| **Audit Vault**| `POST` | `/api/v1/audit/verify` | Bearer JWT | `ADMIN`, `AUDITOR` |
| **Settings** | `GET` | `/api/v1/auth/api-keys` | Bearer JWT | All authenticated users |
| **Settings** | `POST` | `/api/v1/auth/api-keys` | Bearer JWT | All authenticated users |
| **Settings** | `DELETE`| `/api/v1/auth/api-keys/{id}` | Bearer JWT | All authenticated users |
