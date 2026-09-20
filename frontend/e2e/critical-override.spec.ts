import { test, expect } from "@playwright/test";
import { attachTelemetryMonitor, loginAs } from "./helpers";

test.describe("4. CRITICAL Override Invariant Guarantee", () => {
  test("4.1 Invariant: delete_database is denied for unpermitted AND permitted agent with distinct reasons", async ({
    page,
    request,
  }) => {
    attachTelemetryMonitor(page);

    // 1. Get auth token for demo admin
    const loginRes = await request.post("http://127.0.0.1:8000/api/v1/auth/login", {
      data: { email: "admin@agentguard-demo.local", password: "DemoAdmin1!" },
    });
    const { access_token } = await loginRes.json();

    // 2. Register a fresh test agent with its API key
    const agentRes = await request.post("http://127.0.0.1:8000/api/v1/agents", {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { name: `guard-agent-${Date.now()}` },
    });
    const testAgent = await agentRes.json();
    expect(testAgent.api_key).toBeTruthy();

    // 3. Case A: Attempt delete_database WITHOUT permission
    const unpermittedRes = await request.post("http://127.0.0.1:8000/api/v1/guard/check", {
      headers: { "X-API-Key": testAgent.api_key },
      data: {
        agent_id: testAgent.id,
        tool_name: "delete_database",
        action: "delete_database",
        parameters: { target: "all_production_data" },
      },
    });
    expect(unpermittedRes.status()).toBe(200);
    const unpermittedData = await unpermittedRes.json();

    // Invariant: Decision must be DENY
    expect(unpermittedData.decision).toBe("DENY");
    // Denial reason must cite missing permission
    expect(unpermittedData.reason.toLowerCase()).toContain("permission");
    expect(unpermittedData.reason.toLowerCase()).not.toContain("critical");

    // 4. Find tool ID for delete_database
    const toolsRes = await request.get("http://127.0.0.1:8000/api/v1/tools", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const toolsData = await toolsRes.json();
    const toolsList = toolsData.items || toolsData;
    const deleteDbTool = toolsList.find((t: { name: string }) => t.name === "delete_database");
    expect(deleteDbTool).toBeTruthy();

    // 5. Explicitly grant permission for delete_database
    const grantRes = await request.post("http://127.0.0.1:8000/api/v1/permissions", {
      headers: { Authorization: `Bearer ${access_token}` },
      data: {
        agent_id: testAgent.id,
        tool_id: deleteDbTool.id,
      },
    });
    expect(grantRes.ok()).toBe(true);

    // 6. Case B: Attempt delete_database WITH explicit permission
    const permittedRes = await request.post("http://127.0.0.1:8000/api/v1/guard/check", {
      headers: { "X-API-Key": testAgent.api_key },
      data: {
        agent_id: testAgent.id,
        tool_name: "delete_database",
        action: "delete_database",
        parameters: { target: "all_production_data" },
      },
    });
    expect(permittedRes.status()).toBe(200);
    const permittedData = await permittedRes.json();

    // Invariant: Decision must STILL be DENY
    expect(permittedData.decision).toBe("DENY");

    // Invariant: Denial reason MUST cite risk level / policy override, NOT missing permission
    const reasonLower = permittedData.reason.toLowerCase();
    expect(reasonLower).toContain("critical");
    expect(reasonLower).not.toContain("does not have permission");

    // 7. Verify in Audit Vault UI that the decision is recorded as a DENY entry
    await loginAs(page, "AUDITOR");
    await page.goto("/audit", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    const auditTable = page.locator("table");
    await expect(auditTable).toBeVisible();
    await expect(auditTable.getByText("DENY", { exact: true }).first()).toBeVisible();
    // Expand the top row to reveal event_data details including delete_database
    await auditTable.locator("tbody tr").first().click();
    await expect(auditTable.getByText("delete_database", { exact: false })).toBeVisible();
  });
});
