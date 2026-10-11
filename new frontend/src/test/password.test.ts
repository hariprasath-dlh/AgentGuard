import { describe, expect, it } from "vitest";
import { passwordStrength } from "@/lib/password";

describe("password rules", () => {
  it("rejects passwords shorter than 8 characters", () => {
    expect(passwordStrength("Ab1!").valid).toBe(false);
  });
  it("requires a special character", () => {
    expect(passwordStrength("Abcdefg1").valid).toBe(false);
  });
  it("accepts the demo password as Strong", () => {
    expect(passwordStrength("AgentGuard@Demo2026!")).toMatchObject({
      valid: true,
      label: "Strong",
    });
  });
});
