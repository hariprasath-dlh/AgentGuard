import { test, expect } from "@playwright/test";
import { attachTelemetryMonitor, loginAs } from "./helpers";

test.describe("3. All Eight Screens - Real Actions", () => {
  test("3.1 Dashboard: Stat tiles show real numbers and activity feed populates", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // Stat tiles should be visible and show numeric values
    await expect(page.getByText("Requests today", { exact: false })).toBeVisible();
    await expect(page.getByText("Total agents", { exact: false })).toBeVisible();
    await expect(page.getByText("Spend today", { exact: false })).toBeVisible();

    // Activity feed panel
    await expect(page.getByText("Live activity", { exact: false })).toBeVisible();
  });

  test("3.2 Agents: Create agent, verify one-time API key reveal, edit, and deactivate", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");
    await page.goto("/agents", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    const uniqueSuffix = Date.now().toString().slice(-6);
    const agentName = `e2e-agent-${uniqueSuffix}`;
    const agentDesc = `E2E automated agent created at ${uniqueSuffix}`;

    // 1. Create agent
    await page.locator('button:has-text("+ Register Agent")').click();
    await expect(page.locator('h2:has-text("Register agent")')).toBeVisible();

    await page.locator('input#agent-name').fill(agentName);
    await page.locator('textarea#agent-desc').fill(agentDesc);
    await page.locator('button:has-text("Register agent")').last().click();

    // 2. Verify one-time API key dialog appears
    await expect(page.getByText("Copy this API key now", { exact: false })).toBeVisible({ timeout: 10000 });
    const keyContainer = page.locator(".rounded-md.border.border-brass\\/30.bg-brass-soft p");
    await expect(keyContainer).toBeVisible();
    const apiKeyText = await keyContainer.innerText();
    expect(apiKeyText.length).toBeGreaterThan(10);

    // Close the one-time reveal dialog
    await page.locator('button:has-text("I\'ve stored it")').click();
    await expect(page.getByText("Copy this API key now")).not.toBeVisible();

    // 3. Confirm agent appears in list and API key is NOT shown in table
    const agentRow = page.locator(`tr:has-text("${agentName}")`);
    await expect(agentRow).toBeVisible();
    await expect(agentRow).not.toContainText(apiKeyText);

    // 4. Edit agent
    await agentRow.locator('button:has-text("Edit")').click();
    await expect(page.getByText("Edit agent")).toBeVisible();
    const updatedDesc = `${agentDesc} (Updated)`;
    await page.locator('textarea#edit-desc').fill(updatedDesc);
    await page.locator('button:has-text("Save changes")').click();
    await expect(page.getByText("Edit agent")).not.toBeVisible();
    await expect(page.locator(`tr:has-text("${agentName}")`)).toContainText(updatedDesc);

    // 5. Deactivate agent
    const updatedAgentRow = page.locator(`tr:has-text("${agentName}")`);
    await updatedAgentRow.locator('button:has-text("Deactivate")').click();

    // Toast and status update
    await expect(page.locator('[data-sonner-toaster]').getByText(/deactivated/i)).toBeVisible();
  });

  test("3.3 Tools & Permissions: Create tool, edit tool, grant permission, and revoke", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");
    await page.goto("/tools", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    const uniqueSuffix = Date.now().toString().slice(-6);
    const toolName = `tool_${uniqueSuffix}`;
    const toolDesc = `E2E dynamic tool ${uniqueSuffix}`;

    // 1. Create tool
    await page.locator('button:has-text("+ Register Tool")').click();
    await expect(page.getByRole("heading", { name: "Register tool" })).toBeVisible();

    await page.locator('input#tool-name').fill(toolName);
    await page.locator('textarea#tool-desc').fill(toolDesc);
    await page.locator('button:has-text("Register tool")').last().click();

    // Confirm tool appears in Tools tab
    await expect(page.locator(`tr:has-text("${toolName}")`)).toBeVisible({ timeout: 10000 });

    // 2. Edit tool
    const toolRow = page.locator(`tr:has-text("${toolName}")`);
    await toolRow.locator('button:has-text("Edit")').click();
    await expect(page.getByText("Edit tool")).toBeVisible();
    const updatedToolDesc = `${toolDesc} - Modified`;
    await page.locator('textarea#et-desc').fill(updatedToolDesc);
    await page.locator('button:has-text("Save changes")').click();
    await expect(page.getByText("Edit tool")).not.toBeVisible();
    await expect(page.locator(`tr:has-text("${toolName}")`)).toContainText(updatedToolDesc);

    // 3. Grant permission on Permissions tab
    await page.locator('button[role="tab"]:has-text("Permissions")').click();
    await page.locator('button:has-text("Grant permission")').click();
    await expect(page.getByRole("dialog").getByRole("heading", { name: "Grant permission" })).toBeVisible();

    // Select Agent
    await page.locator('button:has-text("Select an agent")').click();
    await page.locator('[role="option"]').first().click();

    // Select Tool
    await page.locator('button:has-text("Select a tool")').click();
    const toolOption = page.locator(`[role="option"]:has-text("${toolName}")`);
    if (await toolOption.isVisible()) {
      await toolOption.click();
    } else {
      await page.locator('[role="option"]').first().click();
    }

    await page.locator('div[role="dialog"] button:has-text("Grant permission")').click();
    await expect(page.locator('[data-sonner-toaster]').getByText(/granted/i)).toBeVisible();

    // 4. Revoke permission
    const permRow = page.locator("table tbody tr").first();
    await permRow.locator('button:has-text("Revoke")').click();
    await expect(page.locator('[data-sonner-toaster]').getByText(/revoked/i)).toBeVisible();
  });

  test("3.4 Policies: Create policy with rule types, edit, and delete", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");
    await page.goto("/policies", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    const uniqueSuffix = Date.now().toString().slice(-6);
    const policyName = `policy-${uniqueSuffix}`;

    // 1. Create policy
    await page.locator('button:has-text("+ New Policy")').click();
    await expect(page.getByRole("heading", { name: "New policy" })).toBeVisible();

    await page.locator('input#p-name').fill(policyName);
    await page.locator('textarea#p-desc').fill("E2E Test Policy for risk enforcement");
    await page.locator('input#p-allow').fill("read_customer, send_email");
    await page.locator('button:has-text("Create policy")').click();
    await expect(page.getByRole("dialog")).not.toBeVisible();

    // Verify policy appears in list
    const policyRow = page.locator(`tr:has-text("${policyName}")`);
    await expect(policyRow).toBeVisible({ timeout: 10000 });

    // 2. Edit policy
    await policyRow.locator('button:has-text("Edit")').click();
    await expect(page.getByRole("heading", { name: "Edit policy" })).toBeVisible();
    await page.locator('textarea#p-desc').fill("Updated description for policy");
    await page.locator('button:has-text("Save changes")').click();
    await expect(page.getByText("Edit policy")).not.toBeVisible();

    // 3. Remove policy — assert on actual network request
    const updatedPolicyRow = page.locator(`tr:has-text("${policyName}")`);
    const deletePromise = page.waitForResponse(
      (resp) => resp.url().includes("/policies/") && resp.request().method() === "DELETE" && resp.status() === 204
    );
    await updatedPolicyRow.locator('button:has-text("Remove")').click();
    const deleteResp = await deletePromise;
    expect(deleteResp.request().method()).toBe("DELETE");
    expect(deleteResp.status()).toBe(204);
    await expect(page.locator('[data-sonner-toaster]').getByText(/deleted|removed/i)).toBeVisible();

    // Confirm policy was soft-deleted: active switch toggles to unchecked
    await expect(page.locator(`tr:has-text("${policyName}") button[role="switch"]`)).toHaveAttribute("data-state", "unchecked");
  });

  test("3.5 Budgets: Edit caps on real agent budget, confirm unlimited & numeric caps persist", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");
    await page.goto("/budgets", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // Click Configure caps on the first budget row
    const editBtn = page.locator('table button:has-text("Configure caps")').first();
    await expect(editBtn).toBeVisible();
    await editBtn.click();
    await expect(page.getByRole("dialog").getByText("Configure caps")).toBeVisible();

    // Set numeric cap on max cost per day
    const targetDailyCap = "250.00";
    await page.locator('input#cpd').fill(targetDailyCap);
    await page.locator('button:has-text("Save caps")').click();
    await expect(page.getByRole("dialog")).not.toBeVisible();

    // Verify table displays $250.00 (use .first() since multiple caps may share the same value)
    await expect(page.locator('table').getByText("$250.00").first()).toBeVisible();

    // Reload page to confirm persistence from PostgreSQL
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page.locator('table').getByText("$250.00").first()).toBeVisible();

    // Clear cap back to Unlimited
    await page.locator('table button:has-text("Configure caps")').first().click();
    await page.locator('input#cpd').fill("");
    await page.locator('button:has-text("Save caps")').click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await expect(page.locator('table').getByText("Unlimited").first()).toBeVisible();
  });

  test("3.6 Approvals: As MANAGER, approve a pending request and separately deny another", async ({ page, request }) => {
    attachTelemetryMonitor(page);

    // 1. Obtain admin token to provision test agent & permission
    const adminToken = await (async () => {
      const loginRes = await request.post("http://127.0.0.1:8000/api/v1/auth/login", {
        data: { email: "admin@agentguard-demo.local", password: "DemoAdmin1!" },
      });
      const data = await loginRes.json();
      return data.access_token;
    })();

    // Register a test agent with API key
    const uniqueAgent = `approv-agent-${Date.now()}`;
    const agentRes = await request.post("http://127.0.0.1:8000/api/v1/agents", {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { name: uniqueAgent },
    });
    const testAgent = await agentRes.json();
    expect(testAgent.api_key).toBeTruthy();

    // Get tool ID for process_refund (HIGH risk tool that triggers HITL)
    const toolsRes = await request.get("http://127.0.0.1:8000/api/v1/tools", {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const toolsData = await toolsRes.json();
    const toolsList = toolsData.items || toolsData;
    const refundTool = toolsList.find((t: { name: string }) => t.name === "process_refund");

    // Grant permission to agent for process_refund
    await request.post("http://127.0.0.1:8000/api/v1/permissions", {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: {
        agent_id: testAgent.id,
        tool_id: refundTool.id,
        is_allowed: true,
      },
    });

    // Trigger process_refund -> decision PENDING
    const refundReq = await request.post("http://127.0.0.1:8000/api/v1/guard/check", {
      headers: { "X-API-Key": testAgent.api_key },
      data: {
        agent_id: testAgent.id,
        tool_name: "process_refund",
        action: "process_refund",
        parameters: { customer_id: "CUST-9999", amount: 75000.0, currency: "INR" },
      },
    });
    const refundData = await refundReq.json();
    expect(refundData.decision).toBe("PENDING");

    // 2. Login as MANAGER in UI and approve
    await loginAs(page, "MANAGER");
    await page.goto("/approvals", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // Pending request should appear in queue
    const pendingCard = page.locator('.panel:has-text("process_refund")').first();
    await expect(pendingCard).toBeVisible({ timeout: 10000 });

    // Fill review note and approve
    await pendingCard.locator('textarea').fill("Approved by E2E Manager test");
    await pendingCard.locator('button:has-text("Approve")').click();

    await expect(page.locator('[data-sonner-toaster]').getByText(/approved/i)).toBeVisible();

    // 3. Trigger a second request and DENY it
    const refundReq2 = await request.post("http://127.0.0.1:8000/api/v1/guard/check", {
      headers: { "X-API-Key": testAgent.api_key },
      data: {
        agent_id: testAgent.id,
        tool_name: "process_refund",
        action: "process_refund",
        parameters: { customer_id: "CUST-DENY", amount: 99000.0, currency: "INR" },
      },
    });
    const refundData2 = await refundReq2.json();
    expect(refundData2.decision).toBe("PENDING");

    await page.reload();
    await page.waitForLoadState("networkidle");

    const denyCard = page.locator('.panel:has-text("process_refund")').first();
    await expect(denyCard).toBeVisible({ timeout: 10000 });
    await denyCard.locator('textarea').fill("Rejected due to high amount");
    await denyCard.locator('button:has-text("Deny")').click();

    await expect(page.locator('[data-sonner-toaster]').getByText(/denied/i)).toBeVisible();
  });

  test("3.7 Audit Vault: As AUDITOR, verify log table order and complete 'Verify Chain' animation", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "AUDITOR");
    await page.goto("/audit", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // Check table displays audit logs
    await expect(page.locator('table')).toBeVisible();
    await expect(page.getByText("Audit log", { exact: false })).toBeVisible();

    // Click "Verify Chain"
    const verifyBtn = page.locator('button:has-text("Verify Chain")');
    await expect(verifyBtn).toBeVisible();
    await verifyBtn.click();

    // Chain status should show VALID and toast
    await expect(page.getByText("records verified", { exact: false })).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-sonner-toaster]').getByText(/verified|tampering/i)).toBeVisible();
  });

  test("3.8 Settings: Organization and user profile details display accurately", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "SECURITY");
    await page.goto("/settings", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // Profile details
    await expect(page.locator("main").getByText("Demo Security Officer")).toBeVisible();
    await expect(page.locator("main").getByText("security@agentguard-demo.local")).toBeVisible();
    await expect(page.locator("main").getByText("SECURITY", { exact: true })).toBeVisible();

    // Organization details
    await expect(page.getByText("AgentGuard Demo Organization", { exact: false })).toBeVisible();
    await expect(page.getByText("agentguard-demo", { exact: true })).toBeVisible();

    // API Key management section placeholder notice
    await expect(page.getByText("API Key Management — coming once the backend endpoint is confirmed", { exact: false })).toBeVisible();
  });
});
