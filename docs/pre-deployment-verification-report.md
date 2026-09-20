# AgentGuard Pre-Deployment Verification Report

**Date:** 2026-09-18  
**Environment:** Full integrated stack (`docker-compose` PostgreSQL 15, Redis 7, FastAPI Core Backend on `:8000`, TanStack/Vite Frontend Control Plane on `:3000`)  
**Test Engine:** Playwright v1.50+ Chromium Desktop (Single Worker, Serial Execution)  
**Seeded Demo Credentials:** All 5 RBAC roles (ADMIN, SECURITY, AUDITOR, MANAGER, DEVELOPER)  

---

## 1. Executive Summary & Verification Matrix

The integrated runtime governance layer was verified end-to-end against real PostgreSQL databases, Redis key-value stores, live backend endpoints, and frontend Control Plane screens.

| Test Suite | Spec File | Total Tests | Passed | Genuine Defects | Test-Only Fixes Applied | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Authentication Suite** | `auth.spec.ts` | 11 | 11 | 0 | 0 | **PASSED** (100%) |
| **2. RBAC Across All Five Roles** | `rbac.spec.ts` | 12 | 12 | 0 | 1 | **PASSED** (100%) |
| **3. CRITICAL Override Guarantee** | `critical-override.spec.ts` | 1 | 1 | 0 | 0 | **PASSED** (100%) |
| **4. Cross-Role Data Consistency** | `cross-role.spec.ts` | 1 | 1 | 0 | 1 | **PASSED** (100%) |
| **5. All Eight Screens (Real Actions)**| `screens.spec.ts` | 8 | 6 | 2 | 4 | **CONDITIONAL** |
| **6. Error, Loading & Empty States** | `error-states.spec.ts` | 3 | 2 | 1 | 2 | **CONDITIONAL** |
| **7. Responsive & Accessibility** | `responsive-a11y.spec.ts` | 23 | 21 | 2 | 0 | **CONDITIONAL** |
| **TOTALS** | | **59** | **54** | **5** | **8** | **91.5% PASS** |

---

## 2. Test-Only Corrections Applied (Non-Application Changes)

Per project guidelines, test failures caused by invalid assertions, strict-mode collisions, or test harness design were fixed directly in the test suite and are detailed below. **No application behavior was altered to make tests pass.**

1. **`frontend/e2e/helpers.ts` (`clearAuthSession`)**:
   - *Issue:* Navigated to `about:blank` before executing `localStorage.clear()`. Browser security partitions `localStorage` by origin, meaning clearing storage while on `about:blank` did not clear the `agentguard_token` for `http://localhost:3000`. When calling `loginAs()` multiple times in sequence within a single test (e.g. in `cross-role.spec.ts`), the browser stayed logged in as the initial user and redirected away from `/login`.
   - *Fix:* Updated `clearAuthSession` to clear `localStorage` and cookies directly on the application origin without switching the browsing context to `about:blank`.
2. **`frontend/e2e/rbac.spec.ts` (Test 2.4 Button Selector)**:
   - *Issue:* Asserted absence of `+ Create Policy`. The actual button rendered in the UI is `+ New Policy`.
   - *Fix:* Updated assertion to check for `+ New Policy`.
3. **`frontend/e2e/screens.spec.ts` (Test 3.3 Strict-Mode Button Collision)**:
   - *Issue:* `getByText("Register tool")` resolved to 3 elements (the trigger button, dialog heading, and modal submit button), triggering a Playwright strict-mode violation.
   - *Fix:* Scoped dialog title assertion to `getByRole("heading", { name: "Register tool" })`.
4. **`frontend/e2e/screens.spec.ts` (Test 3.3 Grant Permission Dialog Collision)**:
   - *Issue:* `getByRole("dialog").getByText("Grant permission")` matched both dialog title and submit button.
   - *Fix:* Scoped to `getByRole("heading", { name: "Grant permission" })`.
5. **`frontend/e2e/screens.spec.ts` (Test 3.4 Strict-Mode Button Collision)**:
   - *Issue:* `getByText("New policy")` matched both `+ New Policy` button and dialog heading `<h2>New policy</h2>`.
   - *Fix:* Scoped to `getByRole("heading", { name: "New policy" })`.
6. **`frontend/e2e/screens.spec.ts` (Test 3.4 Dialog Animation & Edit Policy Assertion)**:
   - *Issue:* Test attempted to click the policy row `Edit` button while the previous Radix dialog closing transition was still intercepting pointer events.
   - *Fix:* Added `await expect(page.getByRole("dialog")).not.toBeVisible()` before interacting with the table row, and used `getByRole("heading", { name: "Edit policy" })`.
7. **`frontend/e2e/screens.spec.ts` (Test 3.4 Soft-Delete Semantic Invariant)**:
   - *Issue:* Test asserted that removing a policy caused the row to be deleted from the DOM (`not.toBeVisible()`). However, AgentGuard's policy engine intentionally implements soft-deletion (`DELETE /policies/{id}` sets `is_active: false`) to preserve audit trail integrity and foreign key resolution for historical tool requests.
   - *Fix:* Updated assertion to verify that the policy row's active switch toggles to `data-state="unchecked"` after removal.
8. **`frontend/e2e/error-states.spec.ts` (Test 7.1 Timeout & CSS Parsing Error)**:
   - *Issue:* Test failed with 8s timeout because React Query defaults to 3 retries with exponential backoff on HTTP 500 errors before displaying the error state. In addition, `h1:has-text('This page didn\'t load')` contained an unescaped apostrophe in the CSS selector string.
   - *Fix:* Increased error state visibility timeout to 15s to allow React Query retry backoff to conclude, and replaced raw CSS selector with `getByRole("heading", { name: "This page didn't load" })`.

---

## 3. Genuine Application Defects Identified

The following genuine defects exist in the application code and require remediation before production deployment.

### Defect 1: Budget Cap API Contract Mismatch (`max_cost` vs `max_budget`)
- **Severity:** HIGH
- **Component:** Frontend (`src/routes/budgets.tsx`, `src/lib/api.ts`) vs Backend (`app/schemas/budget.py`, `app/models/budget.py`)
- **Observed Behavior:** In the Budgets screen, entering a daily cap (e.g. `$250.00`) and clicking "Save caps" appears to succeed, but the table continues to show `Unlimited` and reloads as `Unlimited`.
- **Root Cause:**
  - The frontend form submits `max_cost_per_session` and `max_cost_per_day` to `PATCH /api/v1/budgets/{id}`.
  - The backend FastAPI Pydantic schema `BudgetUpdateRequest` and SQLAlchemy model expect `max_budget_per_session` and `max_budget_per_day`.
  - Because Pydantic ignores extra unknown fields, the payload is accepted with HTTP 200, but no database fields are updated.
  - When fetching `/budgets`, the backend returns `max_budget_per_day`, while the frontend reads `b.max_cost_per_day`, causing values to display as `Unlimited`.
- **Remediation:** Align `src/lib/api.ts` and `src/routes/budgets.tsx` to serialize and deserialize `max_budget_per_session` / `max_budget_per_day` (or add field alias support in backend schemas).

---

### Defect 2: Missing Organization Identity in User Profile Endpoint (`/auth/me`)
- **Severity:** MEDIUM
- **Component:** Backend (`app/schemas/auth.py`, `app/api/auth.py`) vs Frontend (`src/routes/settings.tsx`)
- **Observed Behavior:** On the Settings screen (`/settings`), the Organization card displays `—` for Name and `—` for Slug, displaying only the raw `Organization ID` GUID.
- **Root Cause:**
  - `GET /api/v1/auth/me` serializes the current user using `UserResponse`, which defines `id`, `organization_id`, `role`, `email`, `full_name`, `is_active`, `created_at`.
  - It does not serialize the joined `organization` relationship or include `organization_name` / `organization_slug`.
  - The Settings frontend component attempts `user?.organization?.name ?? user?.organization_name`, which evaluates to `undefined`.
- **Remediation:** Either enrich `UserResponse` in `app/schemas/auth.py` to include `organization_name` and `organization_slug`, or expose a dedicated `GET /api/v1/organizations/me` endpoint.

---

### Defect 3: Non-Unique React Keys During Live Dashboard Rendering
- **Severity:** LOW / CODE HEALTH
- **Component:** Frontend (`src/routes/dashboard.tsx`)
- **Observed Behavior:** During standard screen navigation, React emits repeated console errors:
  `"Encountered two children with the same key, %s. Keys should be unique so that components maintain their identity across updates."`
- **Root Cause:** In `dashboard.tsx`, `utilization.map((u) => <div key={u.agent_id}>)` uses `u.agent_id`. When multiple budget items reference the same agent ID, or when synthetic activity entries share fallback IDs, duplicate keys are mounted in the DOM.
- **Remediation:** Ensure unique keying across activity and utilization lists by using composite keys (e.g. `${u.agent_id}-${index}`).

---

### Defect 4: Horizontal Scrollbar Overflow on Mobile 375px (`/audit`)
- **Severity:** LOW / RESPONSIVENESS
- **Component:** Frontend (`src/routes/audit.tsx`)
- **Observed Behavior:** On mobile viewports (375px width), the Audit Vault screen causes horizontal viewport scrolling (`document.documentElement.scrollWidth > window.innerWidth`).
- **Root Cause:** The table container lacks responsive horizontal scroll containment or flex-wrap on the header action bar (Verify Chain button + filter controls) when rendered on compact screens.
- **Remediation:** Wrap table in `<div className="w-full overflow-x-auto">` and set responsive wrapping classes on the Audit action bar (`flex flex-wrap gap-2`).

---

### Defect 5: Missing Accessible Names on Tool Status Toggles (WCAG 2.1 AA Violation)
- **Severity:** MEDIUM / ACCESSIBILITY
- **Component:** Frontend (`src/routes/tools.tsx`)
- **Observed Behavior:** Axe accessibility scan reported critical failure: `<button role="switch">` toggle elements on the Tools screen lack an accessible label.
- **Root Cause:** The `<Switch />` component in the Tools table is rendered without `aria-label`, `<label>`, or `aria-labelledby`, preventing assistive technologies from communicating which tool is being toggled.
- **Remediation:** Add `aria-label={`Toggle active status for ${tool.name}`}` to the Switch component in `src/routes/tools.tsx`.

---

## 4. Production Readiness Verdict

- **Core Security & Invariant Logic:** **PRODUCTION-READY**
  - All RBAC access controls, route barriers, and role navigation bounds verified across 5 distinct roles.
  - Delete database CRITICAL policy override invariant proven across unpermitted and permitted states.
  - Complete cryptographic hash chain integrity and audit log sequence verified.
  - Human-in-the-loop (HITL) approval and denial workflows verified.
- **Pre-Deployment Action Items:**
  1. Fix budget schema property naming mismatch in frontend (`cost` -> `budget`).
  2. Add organization name/slug to `GET /auth/me` backend response.
  3. Add `aria-label` to tool switches and responsive wrapper to mobile audit vault.
