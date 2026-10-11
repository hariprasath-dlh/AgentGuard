export const passwordChecks = [
  { id: "len", label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { id: "upper", label: "One uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { id: "lower", label: "One lowercase letter", test: (p: string) => /[a-z]/.test(p) },
  { id: "num", label: "One number", test: (p: string) => /\d/.test(p) },
  { id: "special", label: "One special character", test: (p: string) => /[^A-Za-z0-9]/.test(p) },
];

export type Strength = "Weak" | "Fair" | "Good" | "Strong";

export function passwordStrength(p: string): { score: number; label: Strength; valid: boolean } {
  const score = passwordChecks.filter((c) => c.test(p)).length;
  const label: Strength =
    score <= 2 ? "Weak" : score === 3 ? "Fair" : score === 4 ? "Good" : "Strong";
  return { score, label, valid: score === 5 };
}
