import { test, expect } from "@playwright/test";
import { attachTelemetryMonitor, loginAs } from "./helpers";

test.describe("7. Error, Loading, and Empty States", () => {
  test("7.1 Graceful Error State: API 500 failure renders designed error UI without crashing", async ({ page }) => {
    const telemetry = attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");

    // Intercept agents endpoint and return 500 Internal Server Error
    await page.route("**/api/v1/agents", (route) => {
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Simulated Internal Server Error for E2E testing" }),
      });
    });

    await page.goto("/agents");
    await page.waitForLoadState("domcontentloaded");

    // Verify ErrorState component renders error message after React Query retries
    const errorContainer = page.locator(".text-deny:has-text('Simulated Internal Server Error')");
    await expect(errorContainer).toBeVisible({ timeout: 15000 });

    // Verify root layout didn't crash into 404 or TanStack root error boundary
    await expect(page.getByRole("heading", { name: "This page didn't load" })).not.toBeVisible();
  });

  test("7.2 Empty State: Render designed EmptyState when collection is empty", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");

    // Intercept hitl query to return empty array
    await page.route("**/api/v1/hitl?status=PENDING", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/approvals");
    await page.waitForLoadState("networkidle");

    // Verify empty state is rendered
    await expect(page.getByText("Nothing awaiting review", { exact: false })).toBeVisible({ timeout: 8000 });
  });

  test("7.3 Console and Network Error Monitoring: verify no unexpected console errors on clean navigation", async ({ page }) => {
    const telemetry = attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");

    // Cleanly navigate between screens
    const screens = ["/dashboard", "/agents", "/tools", "/policies", "/budgets", "/audit", "/settings"];
    for (const screen of screens) {
      await page.goto(screen, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(400);
    }

    // Filter out expected React dev warnings or telemetry if any
    const criticalConsoleErrors = telemetry.consoleErrors.filter(
      (err) => !err.includes("Download the React DevTools") && !err.includes("Failed to load resource")
    );

    expect(criticalConsoleErrors).toEqual([]);
  });
});
