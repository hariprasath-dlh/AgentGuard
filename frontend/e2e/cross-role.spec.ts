import { test, expect } from "@playwright/test";
import { attachTelemetryMonitor, loginAs } from "./helpers";

test.describe("5. Cross-Role Data Consistency Check", () => {
  test("5.1 Data displayed to SECURITY and AUDITOR on /agents is identical while action buttons differ", async ({
    page,
  }) => {
    attachTelemetryMonitor(page);

    // 1. View /agents as SECURITY
    await loginAs(page, "SECURITY");
    await page.goto("/agents", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // Extract agent table rows data
    const securityAgents = await page.locator("table tbody tr").evaluateAll((rows) =>
      rows.map((row) => ({
        name: row.querySelector("td:nth-child(1)")?.textContent?.trim() || "",
        id: row.querySelector("td:nth-child(2)")?.textContent?.trim() || "",
        status: row.querySelector("td:nth-child(3)")?.textContent?.trim() || "",
        spend: row.querySelector("td:nth-child(4)")?.textContent?.trim() || "",
        cap: row.querySelector("td:nth-child(5)")?.textContent?.trim() || "",
        hasEdit: Array.from(row.querySelectorAll("button")).some((b) => b.textContent?.includes("Edit")),
        hasDeactivate: Array.from(row.querySelectorAll("button")).some((b) => b.textContent?.includes("Deactivate")),
      }))
    );

    expect(securityAgents.length).toBeGreaterThan(0);
    expect(securityAgents.every((a) => a.hasEdit)).toBe(true);

    // 2. View /agents as AUDITOR
    await loginAs(page, "AUDITOR");
    await page.goto("/agents", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    const auditorAgents = await page.locator("table tbody tr").evaluateAll((rows) =>
      rows.map((row) => ({
        name: row.querySelector("td:nth-child(1)")?.textContent?.trim() || "",
        id: row.querySelector("td:nth-child(2)")?.textContent?.trim() || "",
        status: row.querySelector("td:nth-child(3)")?.textContent?.trim() || "",
        spend: row.querySelector("td:nth-child(4)")?.textContent?.trim() || "",
        cap: row.querySelector("td:nth-child(5)")?.textContent?.trim() || "",
        hasEdit: Array.from(row.querySelectorAll("button")).some((b) => b.textContent?.includes("Edit")),
        hasDeactivate: Array.from(row.querySelectorAll("button")).some((b) => b.textContent?.includes("Deactivate")),
      }))
    );

    // 3. Verify exact data equality between roles
    expect(auditorAgents.length).toBe(securityAgents.length);
    for (let i = 0; i < securityAgents.length; i++) {
      expect(auditorAgents[i].name).toBe(securityAgents[i].name);
      expect(auditorAgents[i].id).toBe(securityAgents[i].id);
      expect(auditorAgents[i].status).toBe(securityAgents[i].status);
      expect(auditorAgents[i].spend).toBe(securityAgents[i].spend);
      expect(auditorAgents[i].cap).toBe(securityAgents[i].cap);

      // Verify AUDITOR has NO action buttons
      expect(auditorAgents[i].hasEdit).toBe(false);
      expect(auditorAgents[i].hasDeactivate).toBe(false);
    }
  });
});
