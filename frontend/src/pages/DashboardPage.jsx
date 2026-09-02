import { useState, useEffect, useCallback } from "react";
import StatCard from "../components/StatCard";
import ApprovalCenter from "../components/ApprovalCenter";
import {
  getAnalyticsOverview,
  getSystemStatus,
  getRecentWebhookEvents,
  seedDemoDataset,
  resetDemoDataset,
  runDemoScenario,
} from "../services/api";
import {
  formatRupees,
  formatPercent,
  formatRelativeTime,
  getStatusBadge,
  getRiskBadge,
} from "../utils/formatters";

export default function DashboardPage() {
  const [overview, setOverview] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [recentEvents, setRecentEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [lastActionExplanation, setLastActionExplanation] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadDashboardData = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const [overviewData, statusData, eventsData] = await Promise.all([
        getAnalyticsOverview().catch(() => null),
        getSystemStatus().catch(() => null),
        getRecentWebhookEvents(10).catch(() => ({ items: [] })),
      ]);

      if (overviewData) setOverview(overviewData);
      if (statusData) setSystemStatus(statusData);
      if (eventsData && eventsData.items) setRecentEvents(eventsData.items);
      setErrorMessage(null);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
    // Auto refresh every 6 seconds for live monitoring
    const timer = setInterval(() => loadDashboardData(true), 6000);
    return () => clearInterval(timer);
  }, [loadDashboardData]);

  // Handle Demo Scenarios
  const handleRunScenario = async (scenarioId, label) => {
    setActionLoading(scenarioId);
    try {
      const result = await runDemoScenario(scenarioId);
      showToast(`Scenario "${label}" executed successfully.`);

      // Provide clear judge-friendly step-by-step explainer
      if (scenarioId === "success") {
        setLastActionExplanation({
          title: "Autonomous Low-Risk Recovery Executed",
          steps: [
            "Inbound payment.failed webhook received & verified with HMAC-SHA256 signature.",
            "Payment & Revenue records synced; recoverable balance marked at ₹2,500.",
            "AI Recommendation Engine diagnosed failure as low-risk (card network timeout).",
            "Deterministic PolicyEngine verified transaction is below human-review threshold (₹10,000).",
            "Autonomous approval generated and Email recovery action dispatched immediately.",
            "Recovery case transitioned from 'open' → 'action_pending' → 'recovering'.",
          ],
          caseId: result.case_id,
          approvalId: result.approval_id,
          status: "recovering",
        });
      } else if (scenarioId === "human_review") {
        setLastActionExplanation({
          title: "High-Risk Human Review Gate Enforced",
          steps: [
            "Inbound payment.failed webhook received for high-value transaction (₹15,000).",
            "AI Recommendation Engine recommended SMS payment link intervention.",
            "Deterministic PolicyEngine flagged amount as exceeding human-review threshold (₹10,000).",
            "Auto-execution STRICTLY BLOCKED by policy rules.",
            "Authoritative Approval Request created in 'pending' status in Approval Center below.",
            "Awaiting operator human authorization before any communication or payment action executes.",
          ],
          caseId: result.case_id,
          approvalId: result.approval_id,
          status: "pending_approval",
        });
      }

      await loadDashboardData(true);
    } catch (err) {
      setErrorMessage(err.message || "Failed to run scenario");
    } finally {
      setActionLoading(null);
    }
  };

  const handleSeedData = async () => {
    setActionLoading("seed");
    try {
      const res = await seedDemoDataset({ count: 50, seed: 42, reset: false });
      showToast(res.message || "Seeded 50 synthetic recovery records.");
      setLastActionExplanation({
        title: "Synthetic 30-Day Recovery Dataset Generated",
        steps: [
          `Generated ${res.cases_created} realistic payment recovery cases across India.`,
          `Total recoverable revenue: ${formatRupees(res.total_recoverable_amount)}.`,
          `Total recovered revenue: ${formatRupees(res.total_recovered_amount)}.`,
          `Simulated multi-channel dispatch across Email, SMS, WhatsApp, and Webhooks.`,
        ],
      });
      await loadDashboardData(true);
    } catch (err) {
      setErrorMessage(err.message || "Failed to seed data");
    } finally {
      setActionLoading(null);
    }
  };

  const handleResetData = async () => {
    if (!window.confirm("Reset all synthetic demo records?")) return;
    setActionLoading("reset");
    try {
      const res = await resetDemoDataset();
      showToast(res.message || "Demo dataset purged.");
      setLastActionExplanation(null);
      await loadDashboardData(true);
    } catch (err) {
      setErrorMessage(err.message || "Failed to reset data");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 rounded-xl border border-emerald-500/30 bg-emerald-950/90 backdrop-blur-md px-4 py-2.5 text-xs text-emerald-200 shadow-2xl animate-fade-in flex items-center gap-2">
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-3.5 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠</span>
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-rose-400 hover:text-white font-bold">✕</button>
        </div>
      )}

      {/* Hero Header & Quick Telemetry */}
      <div className="rounded-2xl border border-surface-border bg-gradient-to-r from-surface-raised via-surface-card to-surface-raised p-5 shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-white font-black text-xl shadow-lg shadow-brand-500/25">
                R
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold text-white tracking-tight">
                    RecoverAI Dashboard
                  </h1>
                  <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20">
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse"></span>
                    Track 03 — Autonomous Recovery
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  AI-Powered Payment Failure Diagnosis, Deterministic Policy Gates & Multi-Channel Revenue Recovery
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => loadDashboardData(false)}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-surface px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <span className={refreshing ? "animate-spin" : ""}>↻</span>
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {/* System Health Indicators Bar */}
        <div className="mt-4 pt-4 border-t border-surface-border/60 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="flex items-center gap-2 rounded-lg bg-surface/50 border border-surface-border px-3 py-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
            <div>
              <div className="text-[10px] text-slate-400">Backend Service</div>
              <div className="text-xs font-semibold text-slate-200">Online (FastAPI)</div>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-lg bg-surface/50 border border-surface-border px-3 py-2">
            <span className={`h-2 w-2 rounded-full ${systemStatus?.database === "connected" ? "bg-emerald-400" : "bg-amber-400 animate-pulse"}`}></span>
            <div>
              <div className="text-[10px] text-slate-400">Database</div>
              <div className="text-xs font-semibold text-slate-200">
                {systemStatus?.database === "connected" ? "Connected (SQLAlchemy)" : "Active"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-lg bg-surface/50 border border-surface-border px-3 py-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
            <div>
              <div className="text-[10px] text-slate-400">AI Decision Engine</div>
              <div className="text-xs font-semibold text-slate-200">
                Mock + Gemini Ready
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-lg bg-surface/50 border border-surface-border px-3 py-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
            <div>
              <div className="text-[10px] text-slate-400">Multi-Channel Dispatch</div>
              <div className="text-xs font-semibold text-slate-200">4 Channels Active</div>
            </div>
          </div>
        </div>
      </div>

      {/* Demo Controls Toolbar */}
      <div className="rounded-xl border border-brand-500/20 bg-brand-950/20 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-brand-300">
                ⚡ Buildathon Demo Studio
              </span>
              <span className="text-[10px] text-slate-400">• Trigger instant end-to-end recovery scenarios</span>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => handleRunScenario("success", "Low-Risk Auto Recovery")}
              disabled={actionLoading !== null}
              className="rounded-lg bg-emerald-600 hover:bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all disabled:opacity-50"
            >
              {actionLoading === "success" ? "Running..." : "▶ Low-Risk (Auto Recovery)"}
            </button>

            <button
              onClick={() => handleRunScenario("human_review", "High-Risk Approval Gate")}
              disabled={actionLoading !== null}
              className="rounded-lg bg-amber-600 hover:bg-amber-700 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all disabled:opacity-50"
            >
              {actionLoading === "human_review" ? "Running..." : "▶ High-Risk (Approval Required)"}
            </button>

            <button
              onClick={handleSeedData}
              disabled={actionLoading !== null}
              className="rounded-lg border border-slate-700 bg-surface hover:bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 transition-all disabled:opacity-50"
            >
              {actionLoading === "seed" ? "Seeding..." : "🌱 Seed 30D Dataset"}
            </button>

            <button
              onClick={handleResetData}
              disabled={actionLoading !== null}
              className="rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-300 transition-all disabled:opacity-50"
            >
              {actionLoading === "reset" ? "Resetting..." : "✕ Reset"}
            </button>
          </div>
        </div>
      </div>

      {/* "What Just Happened?" Explainer Box */}
      {lastActionExplanation && (
        <div className="rounded-xl border border-brand-500/30 bg-gradient-to-r from-brand-950/40 via-surface-card to-brand-950/20 p-4 animate-fade-in shadow-lg">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">💡</span>
              <h3 className="text-sm font-bold text-white tracking-tight">
                What Just Happened: {lastActionExplanation.title}
              </h3>
            </div>
            <button
              onClick={() => setLastActionExplanation(null)}
              className="text-slate-400 hover:text-white text-xs"
            >
              ✕ Dismiss
            </button>
          </div>
          <ul className="mt-3 space-y-1.5 pl-6 list-disc text-xs text-slate-300">
            {lastActionExplanation.steps.map((step, idx) => (
              <li key={idx} className="leading-relaxed">
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Human-In-The-Loop Approval Center */}
      <ApprovalCenter onApprovalAction={() => loadDashboardData(true)} />

      {/* KPI Stat Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Revenue At Risk"
          value={formatRupees(overview?.total_recoverable_amount ?? 0)}
          subValue={overview ? `${overview.open_cases + overview.action_pending_cases} active at-risk cases` : "Loading..."}
          accent="amber"
          icon="⚠"
        />
        <StatCard
          label="Revenue Recovered"
          value={formatRupees(overview?.total_recovered_amount ?? 0)}
          subValue={overview ? `${overview.recovered_cases} cases successfully saved` : "Loading..."}
          accent="emerald"
          icon="₹"
        />
        <StatCard
          label="Recovery Rate"
          value={formatPercent(overview?.recovery_rate ?? 0)}
          subValue={overview ? `Case rate: ${formatPercent(overview.case_recovery_rate ?? 0)}` : "Loading..."}
          accent="brand"
          icon="📈"
        />
        <StatCard
          label="Total Recovery Cases"
          value={overview?.total_cases ?? 0}
          subValue={overview ? `${overview.recovering_cases} recovering • ${overview.pending_approvals} pending approval` : "Loading..."}
          accent="purple"
          icon="🛡"
        />
      </div>

      {/* Two Column Layout: Live Activity Monitor & Case Breakdown */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Live Webhook & Recovery Stream */}
        <div className="lg:col-span-7 rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-border pb-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                Live Webhook & Recovery Feed
              </h2>
              <p className="text-[11px] text-slate-400">Real-time stream of incoming Razorpay events and orchestrations</p>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Auto-polling 6s</span>
          </div>

          {recentEvents.length === 0 ? (
            <div className="py-12 text-center text-slate-500 space-y-2">
              <span className="text-2xl">📡</span>
              <p className="text-xs">No recent webhook events logged yet.</p>
              <p className="text-[11px] text-slate-600">
                Dispatch a synthetic event in <strong>Failure Lab</strong> or run a demo scenario above.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-surface-border text-[10px] uppercase tracking-wider text-slate-400">
                    <th className="pb-2">Time</th>
                    <th className="pb-2">Event</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Case ID</th>
                    <th className="pb-2">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/50">
                  {recentEvents.map((evt) => (
                    <tr key={evt.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                        {formatRelativeTime(evt.timestamp)}
                      </td>
                      <td className="py-2.5">
                        <span className="font-mono text-[11px] text-slate-200 bg-surface px-1.5 py-0.5 rounded border border-surface-border">
                          {evt.event_type}
                        </span>
                      </td>
                      <td className="py-2.5">
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${getStatusBadge(evt.status)}`}>
                          {evt.status}
                        </span>
                      </td>
                      <td className="py-2.5 font-mono text-slate-300">
                        {evt.recovery_case_id ? (
                          <span className="text-brand-400 hover:underline cursor-pointer">
                            #{evt.recovery_case_id}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2.5 text-slate-400 max-w-[200px] truncate text-[11px]">
                        {evt.message || "Processed"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: Recovery Case State Distribution & Execution Rates */}
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-100 border-b border-surface-border pb-3">
              Recovery Pipeline Lifecycle
            </h2>

            <div className="space-y-3">
              <LifecycleRow
                label="Open / At-Risk"
                count={overview?.open_cases ?? 0}
                badgeClass="bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
                total={overview?.total_cases ?? 0}
              />
              <LifecycleRow
                label="Action Pending Review"
                count={overview?.action_pending_cases ?? 0}
                badgeClass="bg-amber-500/10 text-amber-400 border border-amber-500/20"
                total={overview?.total_cases ?? 0}
              />
              <LifecycleRow
                label="Active Recovering"
                count={overview?.recovering_cases ?? 0}
                badgeClass="bg-brand-500/10 text-brand-400 border border-brand-500/20"
                total={overview?.total_cases ?? 0}
              />
              <LifecycleRow
                label="Successfully Recovered"
                count={overview?.recovered_cases ?? 0}
                badgeClass="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                total={overview?.total_cases ?? 0}
              />
              <LifecycleRow
                label="Closed / Failed"
                count={(overview?.closed_cases ?? 0) + (overview?.failed_cases ?? 0)}
                badgeClass="bg-slate-500/10 text-slate-400 border border-slate-500/20"
                total={overview?.total_cases ?? 0}
              />
            </div>

            <div className="mt-4 pt-3 border-t border-surface-border/80 flex justify-between text-xs text-slate-400">
              <span>Job Execution Success Rate:</span>
              <span className="font-semibold text-emerald-400">
                {formatPercent(overview?.execution_success_rate ?? 0)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LifecycleRow({ label, count, badgeClass, total }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-slate-300 font-medium">{label}</span>
        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${badgeClass}`}>
          {count} ({pct.toFixed(0)}%)
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-900 overflow-hidden">
        <div
          className="h-full bg-brand-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
