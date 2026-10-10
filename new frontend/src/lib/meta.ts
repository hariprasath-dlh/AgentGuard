export const pageMeta = (title: string, description: string) => ({
  meta: [
    { title: `${title} — AgentGuard` },
    { name: "description", content: description },
    { property: "og:title", content: `${title} — AgentGuard` },
    { property: "og:description", content: description },
  ],
});
