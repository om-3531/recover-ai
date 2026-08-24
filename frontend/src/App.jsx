import { Routes, Route } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout";
import DashboardPage from "./pages/DashboardPage";
import PlaceholderPage from "./pages/PlaceholderPage";

const PLACEHOLDER_PAGES = [
  {
    path: "/payments",
    title: "Payments",
    description: "Failed and at-risk payments will be listed here.",
  },
  {
    path: "/recovery-queue",
    title: "Recovery Queue",
    description: "Cases queued for automated or manual recovery actions.",
  },
  {
    path: "/ai-decisions",
    title: "AI Decisions",
    description: "A log of every AI recommendation and its outcome.",
  },
  {
    path: "/analytics",
    title: "Analytics",
    description: "Recovery performance trends and breakdowns over time.",
  },
  {
    path: "/audit-trail",
    title: "Audit Trail",
    description: "A full record of every decision and action taken by the system.",
  },
  {
    path: "/failure-lab",
    title: "Failure Lab",
    description: "Simulate and inspect payment failure scenarios in test mode.",
  },
  {
    path: "/settings",
    title: "Settings",
    description: "Configuration for policies, integrations, and notifications.",
  },
];

export default function App() {
  return (
    <DashboardLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        {PLACEHOLDER_PAGES.map(({ path, title, description }) => (
          <Route
            key={path}
            path={path}
            element={<PlaceholderPage title={title} description={description} />}
          />
        ))}
      </Routes>
    </DashboardLayout>
  );
}
