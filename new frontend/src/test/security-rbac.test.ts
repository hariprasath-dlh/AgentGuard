import { describe, expect, it } from "vitest";
import { passwordChecks, passwordStrength } from "@/lib/password";
import { ACCESS, accessFor, canCreate, canMutate, canRead, type Role } from "@/lib/rbac";

describe("Security, RBAC & Data Sanitization Audit", () => {
  describe("Password Policy Security Standard", () => {
    it("enforces all 5 security checks individually", () => {
      // 1. Length >= 8
      const lenCheck = passwordChecks.find((c) => c.id === "len");
      expect(lenCheck?.test("short1!")).toBe(false);
      expect(lenCheck?.test("lengthEight1!")).toBe(true);

      // 2. Uppercase
      const upperCheck = passwordChecks.find((c) => c.id === "upper");
      expect(upperCheck?.test("lowercase123!")).toBe(false);
      expect(upperCheck?.test("Uppercase123!")).toBe(true);

      // 3. Lowercase
      const lowerCheck = passwordChecks.find((c) => c.id === "lower");
      expect(lowerCheck?.test("UPPERCASE123!")).toBe(false);
      expect(lowerCheck?.test("Uppercase123!")).toBe(true);

      // 4. Number
      const numCheck = passwordChecks.find((c) => c.id === "num");
      expect(numCheck?.test("NoNumberHere!")).toBe(false);
      expect(numCheck?.test("WithNumber1!")).toBe(true);

      // 5. Special character
      const specialCheck = passwordChecks.find((c) => c.id === "special");
      expect(specialCheck?.test("NoSpecial1234")).toBe(false);
      expect(specialCheck?.test("WithSpecial1234!")).toBe(true);
    });

    it("evaluates strength classification accurately", () => {
      expect(passwordStrength("abc").label).toBe("Weak");
      expect(passwordStrength("Abcdefgh").label).toBe("Fair");
      expect(passwordStrength("Abcdefgh1").label).toBe("Good");
      expect(passwordStrength("Abcdefgh1!").label).toBe("Strong");
    });
  });

  describe("Role Hierarchy & Permitted Roles", () => {
    const validRoles: Role[] = ["ADMIN", "SECURITY", "AUDITOR", "MANAGER", "DEVELOPER"];

    it("includes standard enterprise governance roles", () => {
      validRoles.forEach((role) => {
        expect(typeof role).toBe("string");
        expect(ACCESS[role]).toBeDefined();
      });
    });

    it("enforces role gating for DEVELOPER", () => {
      expect(canRead("DEVELOPER", "dashboard")).toBe(false);
      expect(canRead("DEVELOPER", "agents")).toBe(true);
      expect(canCreate("DEVELOPER", "agents")).toBe(true);
      expect(canMutate("DEVELOPER", "agents")).toBe(false);
      expect(canRead("DEVELOPER", "policies")).toBe(false);
      expect(canRead("DEVELOPER", "approvals")).toBe(false);
      expect(canRead("DEVELOPER", "audit")).toBe(false);
    });

    it("enforces role gating for AUDITOR", () => {
      expect(canRead("AUDITOR", "dashboard")).toBe(true);
      expect(canRead("AUDITOR", "audit")).toBe(true);
      expect(canRead("AUDITOR", "approvals")).toBe(false);
      expect(canMutate("AUDITOR", "agents")).toBe(false);
      expect(accessFor("AUDITOR", "audit")).toBe("write");
    });

    it("enforces role gating for MANAGER", () => {
      expect(canRead("MANAGER", "dashboard")).toBe(true);
      expect(canRead("MANAGER", "approvals")).toBe(true);
      expect(accessFor("MANAGER", "approvals")).toBe("write");
      expect(canRead("MANAGER", "audit")).toBe(false);
    });

    it("enforces role gating for SECURITY", () => {
      expect(canRead("SECURITY", "dashboard")).toBe(true);
      expect(canRead("SECURITY", "agents")).toBe(true);
      expect(canRead("SECURITY", "tools")).toBe(true);
      expect(canRead("SECURITY", "policies")).toBe(true);
      expect(canRead("SECURITY", "budgets")).toBe(true);
      expect(canRead("SECURITY", "approvals")).toBe(false);
      expect(canRead("SECURITY", "audit")).toBe(false);
    });

    it("enforces full administrative access for ADMIN", () => {
      expect(canRead("ADMIN", "dashboard")).toBe(true);
      expect(canRead("ADMIN", "approvals")).toBe(true);
      expect(canRead("ADMIN", "audit")).toBe(true);
      expect(canMutate("ADMIN", "policies")).toBe(true);
    });
  });
});
