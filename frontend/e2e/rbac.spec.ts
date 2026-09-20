import { test, expect } from "@playwright/test";
import { attachTelemetryMonitor, loginAs } from "./helpers";

test.describe("2. RBAC Across All Five Roles", () => {
  const ROLE_NAV_EXPECTATIONS = {
    ADMIN: {
      allowedNav: ["Dashboard", "Agents", "Tools & Permissions", "Policies", "Budgets", "Approvals", "Audit Vault", "Settings"],
      forbiddenNav: [],
      forbiddenUrls: [],
    },
    SECURITY: {
      allowedNav: ["Dashboard", "Agents", "Tools & Permissions", "Policies", "Budgets", "Settings"],
      forbiddenNav: ["Approvals", "Audit Vault"],
      forbiddenUrls: ["/approvals", "/audit"],
    },
    AUDITOR: {
      allowedNav: ["Dashboard", "Agents", "Tools & Permissions", "Policies", "Budgets", "Audit Vault", "Settings"],
      forbiddenNav: ["Approvals"],
      forbiddenUrls: ["/approvals"],
    },
    MANAGER: {
      allowedNav: ["Dashboard", "Agents", "Tools & Permissions", "Policies", "Budgets", "Approvals", "Settings"],
      forbiddenNav: ["Audit Vault"],
      forbiddenUrls: ["/audit"],
    },
    DEVELOPER: {
      allowedNav: ["Agents", "Tools & Permissions", "Settings"],
      forbiddenNav: ["Dashboard", "Policies", "Budgets", "Approvals", "Audit Vault"],
      forbiddenUrls: ["/dashboard", "/policies", "/budgets", "/approvals", "/audit"],
    },
  };

  for (const [role, expectations] of Object.entries(ROLE_NAV_EXPECTATIONS)) {
    test(`2.1 ${role} navigation links match RBAC matrix`, async ({ page }) => {
      attachTelemetryMonitor(page);
      await loginAs(page, role as keyof typeof ROLE_NAV_EXPECTATIONS);

      // On mobile, the sidebar (aside) is CSS-hidden behind a hamburger drawer
      const asideVisible = await page.locator("aside").isVisible();
      if (!asideVisible) {
        // Open the mobile Sheet drawer
        await page.locator('button[aria-label="Open menu"]').click();
        await page.waitForTimeout(500);
      }

      // On desktop: aside nav. On mobile: the open Sheet drawer nav
      const navLocator = asideVisible
        ? page.locator("aside nav")
        : page.getByRole("dialog").locator("nav");
      await expect(navLocator).toBeVisible({ timeout: 8000 });

      // Check allowed nav links
      for (const item of expectations.allowedNav) {
        await expect(navLocator.getByText(item, { exact: true })).toBeVisible();
      }

      // Check forbidden nav links are NOT visible in sidebar
      for (const item of expectations.forbiddenNav) {
        await expect(navLocator.getByText(item, { exact: true })).not.toBeVisible();
      }
    });



    test(`2.2 ${role} direct URL navigation to forbidden routes renders RestrictedState`, async ({ page }) => {
      attachTelemetryMonitor(page);
      await loginAs(page, role as keyof typeof ROLE_NAV_EXPECTATIONS);

      for (const forbiddenUrl of expectations.forbiddenUrls) {
        await page.goto(forbiddenUrl, { waitUntil: "domcontentloaded" });
        await page.waitForLoadState("domcontentloaded");

        // Verify RestrictedState component is displayed
        await expect(page.getByText("Access restricted", { exact: false })).toBeVisible({ timeout: 8000 });
        await expect(page.getByText("Your role does not include permission", { exact: false })).toBeVisible();
      }
    });
  }

  test("2.3 Role mutation permissions: DEVELOPER can create agents but cannot edit/deactivate", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "DEVELOPER");
    await page.goto("/agents", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // DEVELOPER can see "+ Register Agent"
    await expect(page.locator('button:has-text("+ Register Agent")')).toBeVisible();

    // DEVELOPER cannot see Edit or Deactivate buttons on agent rows
    const actionButtons = page.locator('table button:has-text("Edit"), table button:has-text("Deactivate")');
    await expect(actionButtons).toHaveCount(0);
  });

  test("2.4 Role mutation permissions: AUDITOR has read-only view on Policies", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "AUDITOR");
    await page.goto("/policies", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    // AUDITOR cannot see "+ New Policy"
    await expect(page.locator('button:has-text("+ New Policy")')).not.toBeVisible();

    // AUDITOR cannot see Edit or Remove buttons on policy rows
    const editOrRemove = page.locator('table button:has-text("Edit"), table button:has-text("Remove")');
    await expect(editOrRemove).toHaveCount(0);
  });
});
