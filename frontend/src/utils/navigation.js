/**
 * Central navigation config. Used by the Sidebar and by App.jsx to build
 * matching routes, so the two never drift out of sync.
 */
export const NAV_ITEMS = [
  { label: "Dashboard", path: "/" },
  { label: "Payments", path: "/payments" },
  { label: "Recovery Queue", path: "/recovery-queue" },
  { label: "AI Decisions", path: "/ai-decisions" },
  { label: "Analytics", path: "/analytics" },
  { label: "Audit Trail", path: "/audit-trail" },
  { label: "Failure Lab", path: "/failure-lab" },
  { label: "Settings", path: "/settings" },
];
