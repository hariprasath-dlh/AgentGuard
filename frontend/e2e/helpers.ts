import { Page, expect } from "@playwright/test";

export const DEMO_CREDENTIALS = {
  ADMIN: { email: "admin@agentguard-demo.local", password: "DemoAdmin1!", role: "ADMIN", name: "Demo Administrator" },
  SECURITY: { email: "security@agentguard-demo.local", password: "DemoSecurity1!", role: "SECURITY", name: "Demo Security Officer" },
  AUDITOR: { email: "auditor@agentguard-demo.local", password: "DemoAuditor1!", role: "AUDITOR", name: "Demo Compliance Auditor" },
  MANAGER: { email: "manager@agentguard-demo.local", password: "DemoManager1!", role: "MANAGER", name: "Demo Operations Manager" },
  DEVELOPER: { email: "developer@agentguard-demo.local", password: "DemoDeveloper1!", role: "DEVELOPER", name: "Demo Agent Developer" },
} as const;

export type RoleName = keyof typeof DEMO_CREDENTIALS;

export interface CapturedTelemetry {
  consoleErrors: string[];
  consoleWarnings: string[];
  failedRequests: { url: string; status: number; method: string }[];
}

export function attachTelemetryMonitor(page: Page): CapturedTelemetry {
  const telemetry: CapturedTelemetry = {
    consoleErrors: [],
    consoleWarnings: [],
    failedRequests: [],
  };

  page.on("console", (msg) => {
    const text = msg.text();
    if (msg.type() === "error") {
      telemetry.consoleErrors.push(text);
    } else if (msg.type() === "warning") {
      telemetry.consoleWarnings.push(text);
    }
  });

  page.on("response", (resp) => {
    const status = resp.status();
    const url = resp.url();
    if (status >= 400 && !url.includes("/favicon.ico")) {
      telemetry.failedRequests.push({
        url,
        status,
        method: resp.request().method(),
      });
    }
  });

  return telemetry;
}

export async function waitForHydration(page: Page) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);
}

export async function clearAuthSession(page: Page) {
  try {
    await page.context().clearCookies();
    if (!page.url().startsWith("about:blank")) {
      await page.evaluate(() => {
        try {
          localStorage.clear();
          sessionStorage.clear();
        } catch {}
      });
    }
  } catch {}
}

export async function loginAs(page: Page, role: RoleName) {
  const creds = DEMO_CREDENTIALS[role];
  await clearAuthSession(page);
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);

  const emailInput = page.locator("input#email");
  await emailInput.waitFor({ state: "visible", timeout: 8000 });
  await emailInput.fill(creds.email);

  const passwordInput = page.locator("input#password");
  await passwordInput.fill(creds.password);

  const loginResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/auth/login") && resp.status() === 200,
    { timeout: 15000 }
  );

  await page.locator('button[type="submit"]:has-text("Sign in")').click();
  await loginResponsePromise;

  // Wait for navigation away from /login
  await expect(page).not.toHaveURL(/\/login/, { timeout: 12000 });
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(500);
}
