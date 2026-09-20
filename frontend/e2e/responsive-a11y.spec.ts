import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { attachTelemetryMonitor, loginAs } from "./helpers";

test.describe("6. Responsive and Accessibility Suite", () => {
  const CORE_SCREENS = ["/dashboard", "/agents", "/approvals", "/audit"];
  const VIEWPORTS = [
    { name: "mobile-375px", width: 375, height: 667 },
    { name: "tablet-768px", width: 768, height: 1024 },
    { name: "desktop-1440px", width: 1440, height: 900 },
  ];

  for (const vp of VIEWPORTS) {
    for (const screen of CORE_SCREENS) {
      test(`6.1 Layout integrity at ${vp.name} on ${screen}`, async ({ page }) => {
        attachTelemetryMonitor(page);
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await loginAs(page, "ADMIN");
        await page.goto(screen, { waitUntil: "domcontentloaded" });
        await page.waitForLoadState("networkidle");

        // Verify page header is rendered
        await expect(page.locator("h1")).toBeVisible();

        // Check for unwanted horizontal scrollbar overflow on body/html
        const hasHorizontalOverflow = await page.evaluate(() => {
          return document.documentElement.scrollWidth > window.innerWidth + 2;
        });
        expect(hasHorizontalOverflow).toBe(false);
      });
    }
  }

  test("6.2 Mobile drawer navigation functions at 375px", async ({ page }) => {
    attachTelemetryMonitor(page);
    await page.setViewportSize({ width: 375, height: 667 });
    await loginAs(page, "ADMIN");
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // Click mobile hamburger menu
    const menuBtn = page.locator('button[aria-label="Open menu"]');
    await expect(menuBtn).toBeVisible();
    await menuBtn.click();

    // Sheet drawer opens
    const drawer = page.locator('[role="dialog"]');
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("Audit Vault")).toBeVisible();

    // Click navigation item
    await drawer.getByText("Audit Vault").click();

    // Verify navigation
    await expect(page).toHaveURL(/\/audit/, { timeout: 8000 });
  });

  const ALL_SCREENS = [
    { name: "Sign In", path: "/login", tab: "signin", auth: false },
    { name: "Create Account", path: "/login", tab: "signup", auth: false },
    { name: "Dashboard", path: "/dashboard", auth: true },
    { name: "Agents", path: "/agents", auth: true },
    { name: "Tools & Permissions", path: "/tools", auth: true },
    { name: "Policies", path: "/policies", auth: true },
    { name: "Budgets", path: "/budgets", auth: true },
    { name: "Approvals", path: "/approvals", auth: true },
    { name: "Audit Vault", path: "/audit", auth: true },
    { name: "Settings", path: "/settings", auth: true },
  ];

  for (const scr of ALL_SCREENS) {
    test(`6.3 Axe WCAG Accessibility scan on ${scr.name}`, async ({ page }) => {
      attachTelemetryMonitor(page);
      if (scr.auth) {
        await loginAs(page, "ADMIN");
        await page.goto(scr.path, { waitUntil: "domcontentloaded" });
      } else {
        await page.goto(scr.path, { waitUntil: "domcontentloaded" });
        if (scr.tab === "signup") {
          await page.locator('button[role="tab"]:has-text("Create account")').click();
        }
      }
      await page.waitForLoadState("networkidle");

      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();

      if (accessibilityScanResults.violations.length > 0) {
        console.log(`[A11y Violations on ${scr.name}]:`, JSON.stringify(
          accessibilityScanResults.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            nodes: v.nodes.length,
          })),
          null,
          2
        ));
      }

      // Assert zero critical accessibility violations
      const criticalViolations = accessibilityScanResults.violations.filter(
        (v) => v.impact === "critical"
      );
      expect(criticalViolations).toEqual([]);
    });
  }
});
