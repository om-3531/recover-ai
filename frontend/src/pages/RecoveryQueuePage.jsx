import { useState, useEffect, useCallback } from "react";
import {
  listRecoveryCases,
  orchestrateRecoveryCase,
  getRecoveryCaseTimeline,
} from "../services/api";
import {
  formatRupees,
  formatDateTime,
  formatRelativeTime,
  getStatusBadge,
  getRiskBadge,
} from "../utils/formatters";

export default function RecoveryQueuePage() {
  const [cases, setCases] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  // Filters
  const [stateFilter, setStateFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [orchestratingId, setOrchestratingId] = useState(null);

  // Case Timeline Drawer Modal
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(false);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const fetchCases = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const params = { limit: 100 };
      if (stateFilter !== "all") params.state = stateFilter;
      if (priorityFilter !== "all") params.priority = priorityFilter;

      const data = await listRecoveryCases(params);
      setCases(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load recovery cases");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [stateFilter, priorityFilter]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  const handleOrchestrate = async (caseId) => {
    setOrchestratingId(caseId);
    try {
      const res = await orchestrateRecoveryCase(caseId);
      showToast(`Orchestration complete: ${res.message || res.status}`);
      await fetchCases(true);
    } catch (err) {
      setError(`Orchestration failed: ${err.message}`);
    } finally {
      setOrchestratingId(null);
    }
  };

  const handleOpenTimeline = async (caseId) => {
    setSelectedCaseId(caseId);
    setTimelineLoading(true);
    try {
      const res = await getRecoveryCaseTimeline(caseId, 50);
      setTimelineEvents(res.events || []);
    } catch (err) {
      setTimelineEvents([]);
    } finally {
      setTimelineLoading(false);
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

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Recovery Investigation Queue</h1>
          <p className="mt-1 text-sm text-slate-400">
            Cases queued for autonomous intervention, policy evaluation, or operator human approval.
          </p>
        </div>
        <button
          onClick={() => fetchCases(false)}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-surface-raised px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <span className={refreshing ? "animate-spin" : ""}>↻</span>
          {refreshing ? "Refreshing..." : "Refresh Queue"}
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-4 space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-400 font-medium">Case State:</span>
          {[
            { id: "all", label: "All Cases" },
            { id: "open", label: "Open" },
            { id: "action_pending", label: "Action Pending" },
            { id: "recovering", label: "Recovering" },
            { id: "recovered", label: "Recovered" },
            { id: "closed", label: "Closed" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStateFilter(tab.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                stateFilter === tab.id
                  ? "bg-brand-500 text-white shadow-md shadow-brand-500/20"
                  : "bg-surface text-slate-400 hover:text-slate-200 border border-surface-border"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-3.5 text-xs text-rose-300 flex items-center justify-between">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-white font-bold">✕</button>
        </div>
      )}

      {/* Recovery Cases Table */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="flex items-center justify-between text-xs text-slate-400 border-b border-surface-border pb-3">
          <span>Showing {cases.length} of {total} recovery cases</span>
          <span className="text-[11px] text-slate-500">Autonomous workflow governed by Merchant Policy</span>
        </div>

        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="flex items-center gap-3 text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
              <span>Loading recovery cases...</span>
            </div>
          </div>
        ) : cases.length === 0 ? (
          <div className="py-16 text-center text-slate-500 space-y-2">
            <span className="text-3xl">🛡</span>
            <p className="text-sm font-medium text-slate-400">No recovery cases found</p>
            <p className="text-xs text-slate-500">
              Dispatch a test payment failure in Failure Lab or seed demo data to populate cases.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-surface-border text-[10px] uppercase tracking-wider text-slate-400">
                  <th className="pb-3">Case ID</th>
                  <th className="pb-3">Failure Reason</th>
                  <th className="pb-3">Risk Level</th>
                  <th className="pb-3">Priority</th>
                  <th className="pb-3">State</th>
                  <th className="pb-3">Actions Count</th>
                  <th className="pb-3">Created</th>
                  <th className="pb-3 text-right">Workflow</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50">
                {cases.map((c) => (
                  <tr key={c.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 font-semibold">
                      <button
                        onClick={() => handleOpenTimeline(c.id)}
                        className="text-brand-400 hover:text-brand-300 hover:underline flex items-center gap-1 font-mono text-xs"
                      >
                        #{c.id}
                        <span className="text-[10px] text-slate-500 font-sans">🔍</span>
                      </button>
                      <div className="text-[10px] text-slate-500 font-normal">
                        Rev #{c.revenue_record_id}
                      </div>
                    </td>
                    <td className="py-3">
                      <div className="font-medium text-slate-200 capitalize">
                        {c.reason ? c.reason.replace(/_/g, " ") : "Payment Failure"}
                      </div>
                    </td>
                    <td className="py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold capitalize ${getRiskBadge(c.risk_status)}`}>
                        {c.risk_status}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className="capitalize text-slate-300 font-mono text-[11px]">
                        {c.priority}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold capitalize ${getStatusBadge(c.current_state)}`}>
                        {c.current_state ? c.current_state.replace(/_/g, " ") : "open"}
                      </span>
                    </td>
                    <td className="py-3 text-slate-300 font-mono">
                      {c.actions ? c.actions.length : 0}
                    </td>
                    <td className="py-3 text-slate-400 whitespace-nowrap">
                      {formatRelativeTime(c.created_at)}
                    </td>
                    <td className="py-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        {c.current_state !== "recovered" && c.current_state !== "closed" && (
                          <button
                            onClick={() => handleOrchestrate(c.id)}
                            disabled={orchestratingId === c.id}
                            className="rounded-lg bg-brand-500 hover:bg-brand-600 px-2.5 py-1 text-[11px] font-medium text-white transition-colors disabled:opacity-50"
                          >
                            {orchestratingId === c.id ? "Running..." : "⚡ Orchestrate"}
                          </button>
                        )}
                        <button
                          onClick={() => handleOpenTimeline(c.id)}
                          className="rounded-lg border border-slate-700 bg-surface px-2.5 py-1 text-[11px] font-medium text-slate-300 hover:text-white transition-colors"
                        >
                          Timeline
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Case Timeline Drawer / Modal */}
      {selectedCaseId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl rounded-2xl border border-surface-border bg-surface-raised p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>📜</span> Recovery Case #{selectedCaseId} Audit Timeline
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Ordered, immutable audit ledger for this specific recovery case.
                </p>
              </div>
              <button
                onClick={() => setSelectedCaseId(null)}
                className="rounded-lg border border-slate-700 bg-surface px-2.5 py-1 text-xs text-slate-400 hover:text-white"
              >
                ✕ Close
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2">
              {timelineLoading ? (
                <div className="py-12 text-center text-xs text-slate-400 animate-pulse">
                  Loading case audit trail...
                </div>
              ) : timelineEvents.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-500">
                  No audit events recorded for this case yet.
                </div>
              ) : (
                <div className="relative border-l-2 border-brand-500/30 ml-3 space-y-4 pl-4 py-2">
                  {timelineEvents.map((evt) => (
                    <div key={evt.id} className="relative group">
                      <div className="absolute -left-[23px] top-1.5 h-3 w-3 rounded-full bg-brand-500 border-2 border-surface-raised"></div>
                      <div className="rounded-lg border border-surface-border bg-surface p-3 space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-xs text-slate-200">
                            {evt.action ? evt.action.replace(/_/g, " ") : "Action"}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {formatDateTime(evt.timestamp)}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400">
                          Actor: <strong className="text-slate-300 font-mono">{evt.actor}</strong>
                        </div>
                        {evt.event_metadata && Object.keys(evt.event_metadata).length > 0 && (
                          <div className="mt-1.5 rounded bg-slate-950 p-2 font-mono text-[10px] text-slate-400 overflow-x-auto">
                            {JSON.stringify(evt.event_metadata, null, 2)}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-surface-border">
              <button
                onClick={() => setSelectedCaseId(null)}
                className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700"
              >
                Close Timeline
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
