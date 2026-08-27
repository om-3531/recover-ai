import { Routes, Route } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout";
import DashboardPage from "./pages/DashboardPage";
import PolicySettingsPage from "./pages/PolicySettingsPage";
import WebhookConsolePage from "./pages/WebhookConsolePage";
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
];

export default function App() {
  return (
    <DashboardLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/settings" element={<PolicySettingsPage />} />
        <Route path="/failure-lab" element={<WebhookConsolePage />} />
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

