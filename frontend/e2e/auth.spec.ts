import { test, expect } from "@playwright/test";
import { DEMO_CREDENTIALS, attachTelemetryMonitor, clearAuthSession, loginAs, waitForHydration } from "./helpers";

test.describe("1. Authentication Suite", () => {
  test("1.1 Registration input validation (bad email, short password)", async ({ page }) => {
    attachTelemetryMonitor(page);
    await clearAuthSession(page);
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await waitForHydration(page);

    // Click 'Create account' tab
    const signupTab = page.locator('button[role="tab"]:has-text("Create account")');
    await signupTab.waitFor({ state: "visible" });
    await signupTab.click();

    // Fill form with invalid email
    const nameInput = page.locator("input#signup-name");
    await nameInput.waitFor({ state: "visible" });
    await nameInput.fill("Test Candidate");
    await page.locator("input#signup-org").fill("Acme Tests");
    await page.locator("input#signup-email").fill("invalid-email-format");
    await page.locator("input#signup-password").fill("weak");

    // Attempt submit
    await page.locator('button[type="submit"]:has-text("Create account")').click();

    // Check HTML5 input validation for invalid email and password minLength
    const emailValidity = await page.locator("input#signup-email").evaluate((el: HTMLInputElement) => el.validity.valid);
    expect(emailValidity).toBe(false);

    const passwordValidity = await page.locator("input#signup-password").evaluate((el: HTMLInputElement) => el.validity.valid);
    expect(passwordValidity).toBe(false);

    // URL should still be /login
    expect(page.url()).toContain("/login");
  });

  test("1.2 Successful registration flow with genuinely new account", async ({ page }) => {
    attachTelemetryMonitor(page);
    await clearAuthSession(page);
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await waitForHydration(page);

    const uniqueId = Date.now();
    const newEmail = `user_${uniqueId}@agentguard-e2e.local`;
    const newOrg = `Org ${uniqueId}`;

    const signupTab = page.locator('button[role="tab"]:has-text("Create account")');
    await signupTab.waitFor({ state: "visible" });
    await signupTab.click();

    const nameInput = page.locator("input#signup-name");
    await nameInput.waitFor({ state: "visible" });
    await nameInput.fill("E2E Verified User");
    await page.locator("input#signup-org").fill(newOrg);
    await page.locator("input#signup-email").fill(newEmail);
    await page.locator("input#signup-password").fill("ValidPass123!");

    const regResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes("/auth/register") && (resp.status() === 201 || resp.status() === 200),
      { timeout: 15000 }
    );

    await page.locator('button[type="submit"]:has-text("Create account")').click();
    await regResponsePromise;

    // Should receive success toast and land on authenticated route
    await expect(page).not.toHaveURL(/\/login/, { timeout: 15000 });

    // Verify token stored in localStorage
    const token = await page.evaluate(() => localStorage.getItem("agentguard_token"));
    expect(token).toBeTruthy();
  });

  for (const [role, creds] of Object.entries(DEMO_CREDENTIALS)) {
    test(`1.3 Login with demo role: ${role}`, async ({ page }) => {
      attachTelemetryMonitor(page);
      await loginAs(page, role as keyof typeof DEMO_CREDENTIALS);

      // Verify token in localStorage
      const token = await page.evaluate(() => localStorage.getItem("agentguard_token"));
      expect(token).toBeTruthy();

      // Ensure navigated away from /login
      expect(page.url()).not.toContain("/login");

      // Verify user is logged in: either desktop sidebar or mobile header is visible
      const asideVisible = await page.locator("aside").isVisible();
      if (asideVisible) {
        await expect(page.locator("aside").getByText(role, { exact: true })).toBeVisible();
      } else {
        const menuBtn = page.locator('button[aria-label="Open menu"]');
        await expect(menuBtn).toBeVisible({ timeout: 6000 });
      }
    });
  }

  test("1.4 Login with invalid credentials returns specific 401 error", async ({ page }) => {
    attachTelemetryMonitor(page);
    await clearAuthSession(page);
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await waitForHydration(page);

    await page.locator("input#email").fill("admin@agentguard-demo.local");
    await page.locator("input#password").fill("WrongPassword123!");

    const loginFailPromise = page.waitForResponse(
      (resp) => resp.url().includes("/auth/login") && resp.status() === 401,
      { timeout: 15000 }
    );

    await page.locator('button[type="submit"]:has-text("Sign in")').click();
    await loginFailPromise;

    // Verify toast with 401 error message
    const errorToast = page.getByText(/Session expired|Invalid credentials|Sign in failed/i).first();
    await expect(errorToast).toBeVisible({ timeout: 5000 });

    // Ensure we remain on /login and no token is saved
    expect(page.url()).toContain("/login");
    const token = await page.evaluate(() => localStorage.getItem("agentguard_token"));
    expect(token).toBeNull();
  });

  test("1.5 Logout flow clears session and redirects to /login", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");

    // On desktop the Sign out button is in the sidebar; on mobile it is inside the Sheet drawer
    const asideVisible = await page.locator("aside").isVisible();
    if (!asideVisible) {
      // Open the mobile hamburger drawer first
      const menuBtn = page.locator('button[aria-label="Open menu"]');
      await expect(menuBtn).toBeVisible({ timeout: 5000 });
      await menuBtn.click();
      await page.waitForTimeout(400);
    }

    // Click visible 'Sign out' button (visible in aside or in opened mobile drawer)
    const signOutBtn = page.locator('button:has-text("Sign out"):visible');
    await expect(signOutBtn).toBeVisible({ timeout: 5000 });
    await signOutBtn.click();

    // Verify redirect to /login
    await expect(page).toHaveURL(/\/login/, { timeout: 8000 });

    // Verify localStorage cleared
    const token = await page.evaluate(() => localStorage.getItem("agentguard_token"));
    expect(token).toBeNull();
  });

  test("1.6 Protected route redirect: unauthenticated visits redirect to /login", async ({ page }) => {
    attachTelemetryMonitor(page);
    await clearAuthSession(page);

    const protectedRoutes = ["/dashboard", "/agents", "/tools", "/policies", "/budgets", "/approvals", "/audit", "/settings"];
    for (const route of protectedRoutes) {
      try {
        await page.goto(route, { waitUntil: "domcontentloaded" });
      } catch (err: any) {
        if (!err.message?.includes("NS_")) throw err;
      }
      await expect(page).toHaveURL(/\/login/, { timeout: 8000 });
      await page.waitForTimeout(200);
    }
  });

  test("1.7 Authenticated user visiting /login redirects to landing screen", async ({ page }) => {
    attachTelemetryMonitor(page);
    await loginAs(page, "ADMIN");

    // Directly navigate to /login
    await page.goto("/login", { waitUntil: "domcontentloaded" });

    // Should redirect away to /dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 8000 });
  });
});
