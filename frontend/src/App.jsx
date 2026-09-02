import { Routes, Route } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout";
import DashboardPage from "./pages/DashboardPage";
import PaymentsPage from "./pages/PaymentsPage";
import RecoveryQueuePage from "./pages/RecoveryQueuePage";
import AIDecisionsPage from "./pages/AIDecisionsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import AuditTrailPage from "./pages/AuditTrailPage";
import PolicySettingsPage from "./pages/PolicySettingsPage";
import WebhookConsolePage from "./pages/WebhookConsolePage";

export default function App() {
  return (
    <DashboardLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/payments" element={<PaymentsPage />} />
        <Route path="/recovery-queue" element={<RecoveryQueuePage />} />
        <Route path="/ai-decisions" element={<AIDecisionsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/audit-trail" element={<AuditTrailPage />} />
        <Route path="/failure-lab" element={<WebhookConsolePage />} />
        <Route path="/settings" element={<PolicySettingsPage />} />
      </Routes>
    </DashboardLayout>
  );
}
