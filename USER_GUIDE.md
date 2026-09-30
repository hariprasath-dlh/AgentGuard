# AgentGuard — Complete Beginner & User Guide

Welcome to **AgentGuard**! If you are building or running Autonomous AI Agents (using OpenAI, LangChain, CrewAI, AutoGen, or plain Python) and want to make sure they **never run away with your budget, never execute dangerous commands, and always pause for human approval on risky actions**, you are in the right place.

This guide is written in plain, friendly English for developers, product managers, and team leads who are new to AgentGuard.

---

## Table of Contents

1. [What is AgentGuard in Simple Terms?](#1-what-is-agentguard-in-simple-terms)
2. [How Does AgentGuard Work? (The Big Picture)](#2-how-does-agentguard-work-the-big-picture)
3. [Quick Setup: Step-by-Step Guide for New Users](#3-quick-setup-step-by-step-guide-for-new-users)
   - [Step 1: Create an Account & Log In](#step-1-create-an-account--log-in)
   - [Step 2: Understand User Roles (What Role Should You Pick?)](#step-2-understand-user-roles-what-role-should-you-pick)
   - [Step 3: Register Your AI Agent](#step-3-register-your-ai-agent)
   - [Step 4: Register Your Agent's Tools & Assign Risk Levels](#step-4-register-your-agents-tools--assign-risk-levels)
   - [Step 5: Grant Tool Permissions](#step-5-grant-tool-permissions)
   - [Step 6: Configure Spending Budgets & Rate Limits](#step-6-configure-spending-budgets--rate-limits)
4. [How to Use the SDK in Your Existing Python Project](#4-how-to-use-the-sdk-in-your-existing-python-project)
   - [Installation](#installation)
   - [Basic 5-Line Integration](#basic-5-line-integration)
   - [Handling Allowed, Pending (HITL), and Denied Actions](#handling-allowed-pending-hitl-and-denied-actions)
   - [Using with LangChain, CrewAI, or Custom Agents](#using-with-langchain-crewai-or-custom-agents)
5. [How High-Risk Actions & Human Approvals Work (HITL Flow)](#5-how-high-risk-actions--human-approvals-work-hitl-flow)
6. [What Can You Monitor, Visualize, and Control on the Website?](#6-what-can-you-monitor-visualize-and-control-on-the-website)
7. [How Do You "Train" or Customize AgentGuard for Your Use Case?](#7-how-do-you-train-or-customize-agentguard-for-your-use-case)
8. [Frequently Asked Questions (FAQs for First-Time Users)](#8-frequently-asked-questions-faqs-for-first-time-users)

---

## 1. What is AgentGuard in Simple Terms?

Imagine you hired an autonomous virtual employee (an AI agent) that has access to your company credit card, your database, and your email system. 

Without supervision, this agent could:
- Accidentally spend $10,000 on OpenAI API calls in an infinite loop.
- Drop a production database table because a prompt injection tricked it.
- Send unintended refund payments without human verification.

**AgentGuard is the security guard (or bouncer) that stands between your AI agent and the outside world.**

```
┌─────────────────┐       ┌──────────────────────┐       ┌────────────────────────┐
│                 │       │                      │       │                        │
│   AI AGENT      │──────▶│     AGENTGUARD       │──────▶│   ACTUAL TOOL / API    │
│ (Proposes Call) │       │ (Evaluates & Checks) │       │ (Executes ONLY if OK)  │
│                 │       │                      │       │                        │
└─────────────────┘       └──────────────────────┘       └────────────────────────┘
```

> **The golden rule of AgentGuard:**
> **The Agent proposes. AgentGuard decides. The tool executes ONLY after AgentGuard allows it.**

---

## 2. How Does AgentGuard Work? (The Big Picture)

Whenever your AI agent wants to execute an action (like `send_email`, `query_database`, or `process_refund`), it asks AgentGuard: *"Is it safe for me to run this tool with these parameters right now?"*

AgentGuard runs the request through an **11-step security check** in less than 5 milliseconds:

1. **Authentication:** Is the agent's API key valid?
2. **Status Check:** Is the agent Active (not suspended or deleted)?
3. **Permission Check:** Has this agent been given permission to use this specific tool?
4. **Tool Active:** Is this tool currently enabled?
5. **Action Validity:** Is the action clearly specified?
6. **Risk Level Check:** What is the risk level?
   - `LOW` / `MEDIUM` → Automatically **ALLOWED**.
   - `HIGH` → Marked as **PENDING** (Agent pauses for a human manager to approve in the dashboard).
   - `CRITICAL` → Structurally **DENIED** (Even if someone gave the agent permission, CRITICAL tools are always blocked).
7. **Budget Check:** Has the agent exceeded its daily dollar budget or token limit?
8. **Rate Limit:** Has the agent sent too many requests in the last minute?
9. **Parameter Sanitization:** Does the payload contain dangerous SQL injection keywords or shell commands (`DROP TABLE`, `rm -rf`, etc.)?
10. **Heuristic Checks:** Are payload size, token estimates, or costs suspicious?
11. **Cryptographic Audit Vault:** The final decision (ALLOW, DENY, or PENDING) is permanently written to a tamper-evident SHA-256 hash-chain audit log.

---

## 3. Quick Setup: Step-by-Step Guide for New Users

Setting up AgentGuard takes less than 5 minutes:

### Step 1: Create an Account & Log In
1. Open the AgentGuard Web Dashboard (`http://localhost:8080` in local dev, or your production URL).
2. Choose either:
   - **Email & Password:** Enter your email, password, and organization name.
   - **Continue with Google:** One-click sign-in with your Google account.

---

### Step 2: Understand User Roles (What Role Should You Pick?)

AgentGuard comes with 5 built-in enterprise roles:

| Role | Who is this for? | What can they do? |
| :--- | :--- | :--- |
| `ADMIN` | Account owner / Tech Lead | Complete control: create agents, manage tools, configure policies, invite users, view audits. |
| `SECURITY` | Security Officers / DevSecOps | Manage agents, edit risk policies, set budget caps, configure permission grants. |
| `MANAGER` | Business Managers / Supervisors | **Approve or Deny Human-in-the-Loop (HITL) requests** in the approval queue; view stats and agents. |
| `AUDITOR` | Compliance / Legal Teams | Read-only access to all records + **One-click verification of the SHA-256 Cryptographic Audit Vault**. |
| `DEVELOPER` | Software Engineers | Create agents and tools; view dashboard statistics; cannot edit security policies or approve high-risk actions. |

*(When you create a brand new organization, your first account is automatically assigned the `ADMIN` role.)*

---

### Step 3: Register Your AI Agent
1. In the left navigation menu, click **Agents**.
2. Click **Create Agent**.
3. Give your agent a name (e.g., `FinanceBot`) and an optional description.
4. Click **Create**.
5. **IMPORTANT:** You will see a green pop-up showing your **One-Time API Key** (e.g., `ag_live_9a8b7c6d...`). Copy this key immediately and save it in your project's `.env` file! *(AgentGuard hashes keys with SHA-256 and never stores them in plaintext, so it can only be shown once.)*
6. Note down your **Agent UUID** (e.g., `3fa85f64-5717-4562-b3fc-2c963f66afa6`).

---

### Step 4: Register Your Agent's Tools & Assign Risk Levels
1. In the left navigation menu, click **Tools & Permissions**.
2. Click **Create Tool**.
3. Enter the tool's name (e.g., `process_refund`) and choose its **Risk Level**:
   - **LOW:** Safe read-only actions (e.g., `search_kb`, `read_customer_profile`). Runs automatically.
   - **MEDIUM:** Standard operational actions (e.g., `send_confirmation_email`, `create_support_ticket`). Runs automatically.
   - **HIGH:** Risky or financial operations (e.g., `process_refund`, `transfer_funds`, `update_permissions`). **Pauses the agent and asks a Human Manager for approval.**
   - **CRITICAL:** Dangerous destructive operations (e.g., `delete_database`, `wipe_disk`, `export_all_passwords`). **Always blocked by policy.**

---

### Step 5: Grant Tool Permissions
1. Under **Tools & Permissions**, find the **Permission Matrix**.
2. Select your agent (`FinanceBot`) and your tool (`process_refund`).
3. Toggle the permission to **Allowed**.

---

### Step 6: Configure Spending Budgets & Rate Limits
1. In the left navigation menu, click **Budgets**.
2. Click **Edit Budget** next to your agent.
3. Set your guardrails:
   - **Max Budget per Day ($):** e.g., `$50.00`
   - **Max Budget per Session ($):** e.g., `$10.00`
   - **Max Requests per Minute:** e.g., `30 requests/min` (prevents infinite loop runaways)
   - *(Leave blank or 0 for unlimited during development).*

---

## 4. How to Use the SDK in Your Existing Python Project

### Installation

Install the official AgentGuard Python SDK from PyPI:

```bash
pip install agentguard-governance-sdk
```

---

### Basic 5-Line Integration

In your existing Python project, initialize the `AgentGuard` client:

```python
from agentguard import AgentGuard, AgentGuardDenied, AgentGuardPending

# 1. Initialize the client
guard_client = AgentGuard(
    api_key="ag_live_your_api_key_here",       # From Step 3
    agent_id="your-agent-uuid-here",           # From Step 3
    base_url="http://localhost:8000/api/v1",   # Your backend URL
)

# 2. Before running any tool, check with AgentGuard!
try:
    decision = guard_client.guard(
        tool="read_customer",
        parameters={"customer_id": "CUST-1042"},
        estimated_cost=0.01
    )
    
    if decision.allowed:
        # Safe to execute your tool function!
        result = my_actual_read_customer_function(customer_id="CUST-1042")
        print("Tool executed successfully:", result)

except AgentGuardPending as pending:
    # High-risk action was intercepted and sent to human dashboard!
    print(f"Action paused for human approval: {pending.reason}")
    print(f"Tracking Request ID: {pending.request_id}")

except AgentGuardDenied as denied:
    # Action was blocked (Rate limit exceeded, budget reached, or forbidden)
    print(f"Action blocked by AgentGuard: {denied.reason}")
```

---

### Handling Allowed, Pending (HITL), and Denied Actions

The SDK supports two clean coding styles:

#### Style A: Exception Handling (Recommended for strict control)
```python
try:
    guard_client.guard(tool="process_refund", parameters={"amount": 500.0})
    # Run tool
except AgentGuardPending as e:
    # Save state, notify user that approval is pending
    print("Approval pending in dashboard. Request ID:", e.request_id)
except AgentGuardDenied as e:
    # Handle rejection
    print("Action denied:", e.reason)
```

#### Style B: Boolean Inspection (For simple scripts)
```python
result = guard_client.guard(
    tool="process_refund", 
    parameters={"amount": 500.0}, 
    raise_on_blocked=False  # Does not throw exceptions
)

if result.allowed:
    run_tool()
elif result.pending:
    print(f"Human review required! Request ID: {result.request_id}")
else:
    print(f"Blocked: {result.reason}")
```

---

### Using with LangChain, CrewAI, or Custom Agents

If you use **LangChain** or **CrewAI**, you don't need to rewrite your tools. Simply wrap the tool's execution function:

```python
from langchain.tools import tool
from agentguard import AgentGuard

guard_client = AgentGuard(...)

@tool
def process_refund(customer_id: str, amount: float) -> str:
    """Processes a customer refund after governance check."""
    
    # Pre-execution governance check
    decision = guard_client.guard(
        tool="process_refund",
        parameters={"customer_id": customer_id, "amount": amount},
        estimated_cost=amount
    )
    
    # If it was allowed (or after manager approval), execute:
    return actual_stripe_refund(customer_id, amount)
```

---

## 5. How High-Risk Actions & Human Approvals Work (HITL Flow)

Here is exactly what happens when your AI agent attempts a `HIGH`-risk action:

```
[ AI Agent ] 
     │
     ▼
Calls guard(tool="process_refund", amount=$500)
     │
     ▼
[ AgentGuard Backend ] 
Evaluates Policy: Tool is HIGH risk ──▶ Status = PENDING
     │
     ├──────────────────────────────────────────┐
     ▼                                          ▼
[ SDK in Agent Code ]                  [ Web Dashboard / Approvals ]
Raises AgentGuardPending               Approval card appears with:
Agent halts execution safely            • Agent Name: FinanceBot
                                        • Tool: process_refund
                                        • Payload: amount: $500
                                        • Estimated Cost: $500
                                                │
                                                ▼
                                       Human Manager reviews
                                       and clicks [ APPROVE ]
                                                │
                                                ▼
                                    AgentGuard marks as APPROVED
                                    and executes verified mock/tool
```

1. **Agent is paused:** The agent does not execute the refund. It receives a `request_id`.
2. **Dashboard alerts reviewer:** A Manager or Admin logs into the dashboard and clicks **Approvals**.
3. **Manager inspects payload:** The manager inspects the full JSON payload, the reasoning, and the exact cost.
4. **Approve or Deny:**
   - If **Approved:** The status changes to `APPROVED`, notes are logged, and the tool execution proceeds.
   - If **Denied:** The status changes to `DENIED`, and no tool executes.
5. **24-Hour Expiry:** Any pending request not reviewed within 24 hours automatically expires to protect your system.

---

## 6. What Can You Monitor, Visualize, and Control on the Website?

The AgentGuard Web Dashboard gives you complete visibility and control:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENTGUARD CONTROL PLANE                                                   │
├──────────────┬──────────────────────────────────────────────────────────────┤
│  Dashboard   │  • Total Guarded Requests (e.g. 1,420)                       │
│  Agents      │  • Active vs Suspended Agents                                │
│  Tools       │  • Real-Time Spend vs Budget Caps ($14.20 / $100.00)         │
│  Policies    │  • Live Audit Activity Feed (updates every 5 seconds)        │
│  Budgets     │                                                              │
│  Approvals   │  • Human-in-the-Loop Pending Approvals Queue                 │
│  Audit Vault │  • SHA-256 Tamper-Evident Hash Chain Verification            │
│  Settings    │  • One-click Verify Chain Button                             │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

### 1. The Executive Dashboard (`/dashboard`)
- **Live Statistics:** Total requests evaluated, total spend, active agents, and blocked attacks.
- **Real-Time Activity Stream:** Every single tool evaluation stream with color-coded status badges:
  - 🟢 **ALLOW** (Green) — Clean request passed all checks.
  - 🟡 **PENDING** (Yellow) — Waiting for human manager sign-off.
  - 🔴 **DENY** (Red) — Blocked by security policy or budget.

### 2. Agent Management (`/agents`)
- View all agents, their API keys, and their current statuses.
- **Emergency Kill Switch:** Change an agent's status from `ACTIVE` to `SUSPENDED` with one click. A suspended agent is immediately rejected from making any tool calls.

### 3. Approvals Queue (`/approvals`)
- Filter pending actions by agent or risk level.
- Review parameter details and submit review notes with approvals.

### 4. Cryptographic Audit Vault (`/audit`)
- View the immutable ledger of all agent decisions.
- Each record contains `sequence_number`, `current_hash`, and `previous_hash` (forming a blockchain-style SHA-256 chain).
- **One-Click "Verify Chain" Button:** Click to verify that no database administrator or malicious actor has modified or deleted any historical record.

---

## 7. How Do You "Train" or Customize AgentGuard for Your Use Case?

> **Key Concept:** You do **not** train AgentGuard with machine learning weights or datasets.
> AgentGuard is a **deterministic policy control engine**. You configure it through data-driven rules that take effect instantly with **zero downtime**.

Here is how you customize it for your specific company:

### 1. Configure Risk Policies (`/policies`)
You can define custom risk rules for different environments:
- In `Development`, set `HIGH` risk tools to `ALLOW` for rapid testing.
- In `Production`, set `HIGH` risk tools to `HITL` (Human-in-the-loop).

### 2. Parameter Denylist Rules
Add regex denylist patterns to block common attack vectors:
- **SQL Injection Guard:** Blocks queries containing `(?i)\bdrop\s+table\b`, `(?i)\btruncate\b`.
- **System Command Guard:** Blocks shell parameters containing `(?i)\brm\s+-rf\b`, `(?i)\bcurl\s+http\b`.
- **PII Leak Guard:** Blocks parameters containing credit card numbers or SSN patterns.

### 3. Per-Agent Budgets & Rates
- Give your `CustomerSupportBot` a conservative budget of `$10/day` and `15 requests/minute`.
- Give your `DataAnalysisBot` a higher budget of `$200/day` and `120 requests/minute`.

---

## 8. Frequently Asked Questions (FAQs for First-Time Users)

### Q1: Will AgentGuard slow down my AI agent?
**No.** The policy engine evaluates all 11 checks (permissions, risk rules, parameter regexes, and Redis sliding-window counters) in **under 5 milliseconds**. Your agent's LLM generation time (typically 1,000–3,000ms) is hundreds of times longer than AgentGuard's check.

### Q2: What happens if AgentGuard or Redis is temporarily down?
AgentGuard follows a **fail-closed security architecture**:
- If the agent cannot reach AgentGuard, the SDK raises `AgentGuardConnectionError` instead of letting an unverified tool execute.
- The SDK includes built-in safe retry logic (with exponential backoff) for transient network blips.

### Q3: Does AgentGuard store my sensitive customer data?
AgentGuard only receives the tool name and parameter payload needed for governance evaluation. Data is stored securely in your private PostgreSQL database under strict organization isolation.

### Q4: Can an agent call tools directly and bypass AgentGuard?
To guarantee complete security, your agent's execution environment should only have network access to the AgentGuard gateway and mock tool endpoints, rather than holding raw production database credentials. The agent calls tools through the AgentGuard SDK.

### Q5: Can multiple users share the same organization?
**Yes.** When a team member creates an account using your organization slug (or when an Admin invites them), they share the same dashboard, agents, audit vault, and approval queue with permissions determined by their assigned role.

---

## Summary Checklist for Getting Started

1. [ ] Install package: `pip install agentguard-governance-sdk`
2. [ ] Log in to Dashboard (`/login`)
3. [ ] Create your Agent (`/agents`) & save your API Key (`ag_live_...`)
4. [ ] Create your Tools (`/tools`) with Risk Levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
5. [ ] Grant permissions between Agent and Tools (`/permissions`)
6. [ ] Add `guard_client.guard(...)` before calling your tools in Python
7. [ ] Monitor live requests and approvals on the Dashboard!
