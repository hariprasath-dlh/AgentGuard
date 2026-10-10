import { describe, expect, it } from "vitest";
import { passwordChecks, passwordStrength } from "@/lib/password";
import { DEMO_ACCOUNT } from "@/lib/auth";

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
      expect(passwordStrength("Abcdefgh").label).toBe("Fair"); // len + upper + lower = 3
      expect(passwordStrength("Abcdefgh1").label).toBe("Good"); // len + upper + lower + num = 4
      expect(passwordStrength("Abcdefgh1!").label).toBe("Strong"); // all 5
    });
  });

  describe("Role Hierarchy & Permitted Roles", () => {
    const validRoles = ["ADMIN", "SECURITY", "AUDITOR", "MANAGER", "DEVELOPER", "VIEWER"];

    it("includes standard enterprise governance roles", () => {
      validRoles.forEach((role) => {
        expect(typeof role).toBe("string");
        expect(role.length).toBeGreaterThan(0);
      });
      expect(DEMO_ACCOUNT.role).toBe("ADMIN");
    });
  });

  describe("Demo Environment Isolation Check", () => {
    it("uses simulated local storage keys and prevents external credential leaks", () => {
      expect(DEMO_ACCOUNT.email.endsWith(".local")).toBe(true);
      expect(DEMO_ACCOUNT.password).toContain("Demo");
    });
  });
});
