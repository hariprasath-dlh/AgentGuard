import { beforeEach, describe, expect, it, vi } from "vitest";
import { bootstrapSession, exchangeCode, getSession, login, logout, register, type Session } from "@/lib/auth";

describe("Authentication & Account Workflows (Live API Module)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  describe("Live Login Workflow", () => {
    it("successfully authenticates with valid credentials using mocked API", async () => {
      const mockToken = {
        access_token: "mock-jwt-token-12345",
        token_type: "bearer",
        expires_in: 3600,
      };

      const mockUser = {
        id: "user-uuid-1",
        email: "admin@enterprise.io",
        full_name: "Enterprise Admin",
        role: "ADMIN",
        organization_id: "org-uuid-1",
        organization_name: "Enterprise AI Inc",
        organization_slug: "enterprise-ai",
      };

      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(new Response(JSON.stringify(mockToken), { status: 200 }));
        }
        if (url.endsWith("/auth/me")) {
          return Promise.resolve(new Response(JSON.stringify(mockUser), { status: 200 }));
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      });

      const session = await login("admin@enterprise.io", "ValidPass123!", "enterprise-ai");

      expect(session).toBeDefined();
      expect(session.email).toBe("admin@enterprise.io");
      expect(session.role).toBe("ADMIN");
      expect(session.org).toBe("enterprise-ai");
      expect(localStorage.getItem("ag_token")).toBe("mock-jwt-token-12345");

      const active = getSession();
      expect(active.session).not.toBeNull();
      expect(active.expired).toBe(false);
      expect(active.session?.email).toBe("admin@enterprise.io");
    });

    it("rejects login with wrong password without redirecting away", async () => {
      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: "Invalid credentials" }), { status: 401 }),
          );
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      });

      await expect(login("admin@enterprise.io", "WrongPass!", "enterprise-ai")).rejects.toThrow(
        "Invalid credentials",
      );

      // Verify no token was stored
      expect(localStorage.getItem("ag_token")).toBeNull();
    });
  });

  describe("Live Registration Workflow", () => {
    it("registers a new organization account and establishes session", async () => {
      const newUser = {
        name: "Security Auditor",
        email: "auditor@acmecorp.com",
        password: "SecurePassword123!",
        org: "acme-corp",
        orgName: "Acme Corporation",
        role: "AUDITOR",
      };

      const mockRegResp = {
        id: "auditor-uuid",
        email: newUser.email,
        full_name: newUser.name,
        role: "AUDITOR",
        organization_id: "org-uuid-2",
        organization_name: newUser.orgName,
        organization_slug: newUser.org,
      };

      const mockToken = {
        access_token: "mock-auditor-jwt",
        token_type: "bearer",
        expires_in: 3600,
      };

      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url.endsWith("/auth/register")) {
          return Promise.resolve(new Response(JSON.stringify(mockRegResp), { status: 201 }));
        }
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(new Response(JSON.stringify(mockToken), { status: 200 }));
        }
        if (url.endsWith("/auth/me")) {
          return Promise.resolve(new Response(JSON.stringify(mockRegResp), { status: 200 }));
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      });

      const session = await register(newUser);
      expect(session.name).toBe("Security Auditor");
      expect(session.email).toBe("auditor@acmecorp.com");
      expect(session.role).toBe("AUDITOR");
      expect(session.org).toBe("acme-corp");
    });
  });

  describe("Session Expiration & Logout", () => {
    it("clears session and token on explicit logout", () => {
      localStorage.setItem("ag_token", "active-token");
      localStorage.setItem(
        "ag_session",
        JSON.stringify({
          name: "User",
          email: "user@test.io",
          org: "org",
          orgName: "Org",
          role: "ADMIN",
          userId: "123",
          expiresAt: Date.now() + 100000,
        }),
      );

      expect(getSession().session).not.toBeNull();
      logout();
      expect(getSession().session).toBeNull();
      expect(localStorage.getItem("ag_token")).toBeNull();
    });

    it("detects expired session and removes key", () => {
      const expiredSession: Session = {
        name: "Old Session",
        email: "old@test.io",
        org: "org",
        orgName: "Org",
        role: "ADMIN",
        userId: "123",
        expiresAt: Date.now() - 5000,
      };

      localStorage.setItem("ag_session", JSON.stringify(expiredSession));
      localStorage.setItem("ag_token", "expired-token");

      const check = getSession();
      expect(check.session).toBeNull();
      expect(check.expired).toBe(true);
      expect(localStorage.getItem("ag_session")).toBeNull();
      expect(localStorage.getItem("ag_token")).toBeNull();
    });

    it("bootstrapSession syncs role from server and clears on failure", async () => {
      localStorage.setItem("ag_token", "valid-token");

      const serverUser = {
        id: "user-1",
        email: "user@test.io",
        full_name: "Fresh Name",
        role: "MANAGER",
        organization_id: "org-1",
        organization_name: "Org Name",
        organization_slug: "org-slug",
      };

      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url.endsWith("/auth/me")) {
          return Promise.resolve(new Response(JSON.stringify(serverUser), { status: 200 }));
        }
        return Promise.reject(new Error("Network error"));
      });

      const bootstrapped = await bootstrapSession();
      expect(bootstrapped).not.toBeNull();
      expect(bootstrapped?.role).toBe("MANAGER");

      // Failure case: 401 clears session
      globalThis.fetch = vi.fn().mockImplementation(() => {
        return Promise.resolve(new Response(JSON.stringify({ detail: "Invalid token" }), { status: 401 }));
      });

      const failedBootstrap = await bootstrapSession();
      expect(failedBootstrap).toBeNull();
      expect(localStorage.getItem("ag_token")).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // REGRESSION: Google OAuth session persistence (Fix 1)
  // Proves that exchangeCode() stores token+session in localStorage BEFORE
  // navigate() fires, so AppShell.useEffect finds a valid session on mount.
  // ---------------------------------------------------------------------------
  describe("Google OAuth — session persistence after callback (regression Fix 1)", () => {
    it("exchangeCode stores token and session before resolving", async () => {
      const mockExchangeResp = {
        access_token: "google-jwt-token-xyz",
        token_type: "bearer",
        expires_in: 3600,
      };
      const mockUser = {
        id: "google-user-1",
        email: "alice@gmail.com",
        full_name: "Alice",
        role: "ADMIN",
        organization_id: "org-google-1",
        organization_name: "Alice's Workspace",
        organization_slug: "alice-ws-abc123",
      };

      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url.endsWith("/auth/google/exchange")) {
          return Promise.resolve(new Response(JSON.stringify(mockExchangeResp), { status: 200 }));
        }
        if (url.endsWith("/auth/me")) {
          return Promise.resolve(new Response(JSON.stringify(mockUser), { status: 200 }));
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      });

      // localStorage starts empty (simulates fresh OAuth callback page)
      expect(localStorage.getItem("ag_token")).toBeNull();
      expect(getSession().session).toBeNull();

      const session = await exchangeCode("one-time-code-from-backend");

      // Token persisted to localStorage immediately
      expect(localStorage.getItem("ag_token")).toBe("google-jwt-token-xyz");

      // Session stored in localStorage
      expect(getSession().session).not.toBeNull();
      expect(getSession().session?.email).toBe("alice@gmail.com");
      expect(getSession().session?.role).toBe("ADMIN");
      expect(getSession().session?.org).toBe("alice-ws-abc123");

      // Return value is the fully resolved session
      expect(session.email).toBe("alice@gmail.com");
      expect(session.role).toBe("ADMIN");
    });

    it("getSession() returns valid session immediately after exchangeCode resolves — simulating AppShell mount", async () => {
      // Simulates AppShell mounting right after navigate({ to: "/dashboard" })
      const mockExchangeResp = { access_token: "token-abc", token_type: "bearer", expires_in: 3600 };
      const mockUser = {
        id: "u2",
        email: "bob@company.io",
        full_name: "Bob",
        role: "SECURITY",
        organization_id: "org-2",
        organization_name: "Company Inc",
        organization_slug: "company-inc",
      };

      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url.endsWith("/auth/google/exchange"))
          return Promise.resolve(new Response(JSON.stringify(mockExchangeResp), { status: 200 }));
        if (url.endsWith("/auth/me"))
          return Promise.resolve(new Response(JSON.stringify(mockUser), { status: 200 }));
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      });

      await exchangeCode("code-xyz");

      // Simulate AppShell useEffect running synchronously after navigate
      const { session, expired } = getSession();
      expect(session).not.toBeNull();
      expect(expired).toBe(false);
      expect(session?.role).toBe("SECURITY");
      // AppShell would NOT redirect to /login — session is present
    });
  });
});

