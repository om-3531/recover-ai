import { useState, useEffect, useCallback } from "react";
import { listAuditLogs } from "../services/api";
import {
  formatDateTime,
  formatRelativeTime,
} from "../utils/formatters";

export default function AuditTrailPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [entityTypeFilter, setEntityTypeFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("");
  const [expandedLogId, setExpandedLogId] = useState(null);

  const fetchAuditLogs = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const params = { limit: 100 };
      if (entityTypeFilter !== "all") params.entity_type = entityTypeFilter;
      if (actionFilter) params.action = actionFilter;

      const data = await listAuditLogs(params);
      setLogs(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load audit logs");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [entityTypeFilter, actionFilter]);

  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);

  const toggleExpand = (id) => {
    setExpandedLogId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Immutable Audit Trail</h1>
          <p className="mt-1 text-sm text-slate-400">
            Cryptographically logged verification trail for all webhook events, AI decisions, policy evaluations, and recovery executions.
          </p>
        </div>
        <button
          onClick={() => fetchAuditLogs(false)}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-surface-raised px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <span className={refreshing ? "animate-spin" : ""}>↻</span>
          {refreshing ? "Refreshing..." : "Refresh Audit Trail"}
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-surface-border bg-surface-raised p-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-400 font-medium">Entity Type:</span>
          {[
            { id: "all", label: "All Entities" },
            { id: "recovery_case", label: "Recovery Case" },
            { id: "payment", label: "Payment" },
            { id: "payment_event", label: "Webhook Event" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setEntityTypeFilter(tab.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                entityTypeFilter === tab.id
                  ? "bg-brand-500 text-white shadow-md shadow-brand-500/20"
                  : "bg-surface text-slate-400 hover:text-slate-200 border border-surface-border"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative min-w-[220px]">
          <input
            type="text"
            placeholder="Filter by action name..."
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="w-full rounded-lg border border-surface-border bg-surface px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-brand-500 focus:outline-none font-mono"
          />
          {actionFilter && (
            <button
              onClick={() => setActionFilter("")}
              className="absolute right-2.5 top-1.5 text-xs text-slate-400 hover:text-white"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-3.5 text-xs text-rose-300 flex items-center justify-between">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-white font-bold">✕</button>
        </div>
      )}

      {/* Audit Log Table */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="flex items-center justify-between text-xs text-slate-400 border-b border-surface-border pb-3">
          <span>Showing {logs.length} of {total} immutable audit entries</span>
          <span className="text-[11px] text-slate-500 font-mono">Append-only compliance store</span>
        </div>

        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="flex items-center gap-3 text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
              <span>Loading audit logs...</span>
            </div>
          </div>
        ) : logs.length === 0 ? (
          <div className="py-16 text-center text-slate-500 space-y-2">
            <span className="text-3xl">📜</span>
            <p className="text-sm font-medium text-slate-400">No audit logs found</p>
            <p className="text-xs text-slate-500">
              {actionFilter ? "Try clearing the action filter." : "Actions and webhooks will automatically append to this ledger."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-surface-border text-[10px] uppercase tracking-wider text-slate-400">
                  <th className="pb-3">Timestamp</th>
                  <th className="pb-3">Action</th>
                  <th className="pb-3">Entity</th>
                  <th className="pb-3">Entity ID</th>
                  <th className="pb-3">Actor / Source</th>
                  <th className="pb-3 text-right">Metadata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50">
                {logs.map((log) => {
                  const isExpanded = expandedLogId === log.id;
                  const isFailure = log.action && (log.action.includes("failed") || log.action.includes("blocked"));

                  return (
                    <tr key={log.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 text-slate-400 whitespace-nowrap font-mono text-[11px]">
                        <div>{formatDateTime(log.timestamp)}</div>
                        <div className="text-[10px] text-slate-500">
                          {formatRelativeTime(log.timestamp)}
                        </div>
                      </td>
                      <td className="py-3 font-semibold">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-[11px] ${
                          isFailure
                            ? "bg-rose-500/10 text-rose-300 border border-rose-500/20"
                            : "bg-surface text-brand-300 border border-surface-border"
                        }`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="py-3 capitalize text-slate-300">
                        <span className="bg-slate-900 px-2 py-0.5 rounded text-[11px] border border-slate-800">
                          {log.entity_type ? log.entity_type.replace(/_/g, " ") : "system"}
                        </span>
                      </td>
                      <td className="py-3 font-mono text-slate-300">
                        {log.entity_id ? `#${log.entity_id}` : "—"}
                      </td>
                      <td className="py-3 font-mono text-slate-400 text-[11px]">
                        {log.actor || "system"}
                      </td>
                      <td className="py-3 text-right">
                        {log.event_metadata && Object.keys(log.event_metadata).length > 0 ? (
                          <div>
                            <button
                              onClick={() => toggleExpand(log.id)}
                              className="rounded bg-surface px-2 py-1 text-[10px] font-mono text-slate-300 hover:text-white border border-surface-border"
                            >
                              {isExpanded ? "Hide JSON ▲" : "View JSON ▼"}
                            </button>
                            {isExpanded && (
                              <div className="mt-2 text-left rounded-lg bg-slate-950 p-2.5 font-mono text-[10px] text-slate-300 border border-surface-border overflow-x-auto max-w-sm ml-auto">
                                <pre>{JSON.stringify(log.event_metadata, null, 2)}</pre>
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-600 text-[11px]">None</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
