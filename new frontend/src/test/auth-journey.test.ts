import { beforeEach, describe, expect, it } from "vitest";
import { DEMO_ACCOUNT, getSession, googleDemo, login, logout, register } from "@/lib/auth";

describe("Authentication & Account Workflows", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("Demo Account Login", () => {
    it("successfully authenticates with valid demo credentials", () => {
      const session = login(DEMO_ACCOUNT.email, DEMO_ACCOUNT.password, DEMO_ACCOUNT.org);

      expect(session).toBeDefined();
      expect(session.email).toBe(DEMO_ACCOUNT.email);
      expect(session.role).toBe("ADMIN");
      expect(session.org).toBe(DEMO_ACCOUNT.org);

      const active = getSession();
      expect(active.session).not.toBeNull();
      expect(active.expired).toBe(false);
      expect(active.session?.email).toBe(DEMO_ACCOUNT.email);
    });

    it("rejects login with incorrect password", () => {
      expect(() => {
        login(DEMO_ACCOUNT.email, "WrongPassword123!", DEMO_ACCOUNT.org);
      }).toThrow("Invalid email, password, or organization slug.");
    });

    it("rejects login with non-existent user", () => {
      expect(() => {
        login("nobody@agentguard.local", "AgentGuard@Demo2026!", "nonexistent");
      }).toThrow("Invalid email, password, or organization slug.");
    });
  });

  describe("Custom User Registration & Session Management", () => {
    it("registers a new organization account and persists user", () => {
      const newUser = {
        name: "Security Auditor",
        email: "auditor@acmecorp.com",
        password: "SecurePassword123!",
        org: "acme-corp",
        orgName: "Acme Corporation",
        role: "AUDITOR",
      };

      const session = register(newUser);
      expect(session.name).toBe("Security Auditor");
      expect(session.email).toBe("auditor@acmecorp.com");
      expect(session.role).toBe("AUDITOR");
      expect(session.org).toBe("acme-corp");

      logout();
      expect(getSession().session).toBeNull();

      const relogged = login(newUser.email, newUser.password, newUser.org);
      expect(relogged.email).toBe(newUser.email);
    });

    it("prevents duplicate registration for an existing email", () => {
      const user = {
        name: "Developer",
        email: "dev@company.com",
        password: "ValidPass123!",
        org: "company-slug",
        orgName: "Company",
        role: "DEVELOPER",
      };

      register(user);

      expect(() => register(user)).toThrow("An account with this email already exists.");
    });

    it("rejects registering with the demo account email", () => {
      expect(() =>
        register({
          name: "Imposter",
          email: DEMO_ACCOUNT.email,
          password: "SomePassword123!",
          org: "fake-org",
          orgName: "Fake Org",
          role: "ADMIN",
        }),
      ).toThrow("An account with this email already exists.");
    });
  });

  describe("Session Expiration & Logout", () => {
    it("clears session state on logout", () => {
      login(DEMO_ACCOUNT.email, DEMO_ACCOUNT.password, DEMO_ACCOUNT.org);
      expect(getSession().session).not.toBeNull();

      logout();
      expect(getSession().session).toBeNull();
      expect(getSession().expired).toBe(false);
    });

    it("detects expired session and removes key", () => {
      const expiredSession = {
        name: "Old User",
        email: "old@test.local",
        org: "old-org",
        role: "VIEWER",
        expiresAt: Date.now() - 1000,
      };
      localStorage.setItem("agentguard_demo_session", JSON.stringify(expiredSession));

      const check = getSession();
      expect(check.session).toBeNull();
      expect(check.expired).toBe(true);
      expect(localStorage.getItem("agentguard_demo_session")).toBeNull();
    });
  });

  describe("Google Demo Sign-in Simulation", () => {
    it("establishes simulated Google session with VIEWER role", () => {
      const session = googleDemo();
      expect(session.name).toBe("Google Demo User");
      expect(session.email).toBe("google.demo@agentguard.local");
      expect(session.role).toBe("VIEWER");
      expect(getSession().session?.email).toBe("google.demo@agentguard.local");
    });
  });
});
