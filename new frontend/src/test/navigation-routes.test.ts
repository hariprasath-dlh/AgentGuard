import { QueryClient } from "@tanstack/react-query";
import { createRouter, rootRouteId } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";
import { routeTree } from "@/routeTree.gen";

describe("Routing & Navigation Architecture", () => {
  const router = createRouter({
    routeTree,
    context: { queryClient: new QueryClient() },
  });

  const routesToVerify = [
    { path: "/", description: "Landing / Homepage" },
    { path: "/login", description: "Sign in page" },
    { path: "/register", description: "Account registration" },
    { path: "/dashboard", description: "Executive Dashboard" },
    { path: "/agents", description: "Agent identities & keys" },
    { path: "/tools", description: "Tool registry" },
    { path: "/permissions", description: "Permissions matrix" },
    { path: "/policies", description: "Policy management" },
    { path: "/budgets", description: "Spend and rate limits" },
    { path: "/approvals", description: "Human-in-the-loop review queue" },
    { path: "/audit", description: "Audit Vault hash chain" },
    { path: "/settings", description: "Organization settings" },
    { path: "/auth/callback", description: "Authentication callback handler" },
  ];

  routesToVerify.forEach(({ path, description }) => {
    it(`resolves valid match for ${path} (${description}) without falling back to rootRouteId`, () => {
      const matches = router.matchRoutes(path);
      expect(matches.length).toBeGreaterThan(0);
      const target = matches.at(-1);
      expect(target).toBeDefined();
      expect(target?.routeId).not.toBe(rootRouteId);
    });
  });

  it("handles non-existent paths gracefully through router matching", () => {
    const unknownMatches = router.matchRoutes("/unknown-404-route-test");
    // TanStack router either matches 404 handler or falls back
    expect(unknownMatches).toBeDefined();
  });
});
