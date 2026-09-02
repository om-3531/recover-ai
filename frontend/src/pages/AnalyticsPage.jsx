import { useState, useEffect, useCallback } from "react";
import StatCard from "../components/StatCard";
import {
  getAnalyticsOverview,
  getRevenueAnalytics,
  getExecutionAnalytics,
  getApprovalAnalytics,
  getFailureAnalytics,
  getChannelAnalytics,
  getTimelineAnalytics,
} from "../services/api";
import {
  formatRupees,
  formatPercent,
  getStatusBadge,
} from "../utils/formatters";

export default function AnalyticsPage() {
  const [overview, setOverview] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [execution, setExecution] = useState(null);
  const [approvals, setApprovals] = useState(null);
  const [failures, setFailures] = useState(null);
  const [channels, setChannels] = useState([]);
  const [timeline, setTimeline] = useState([]);

  const [timeRange, setTimeRange] = useState("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const fetchAnalytics = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const params = {};
      const now = new Date();
      if (timeRange === "today") {
        params.start_date = new Date(now.setHours(0, 0, 0, 0)).toISOString();
      } else if (timeRange === "7d") {
        const d = new Date();
        d.setDate(d.getDate() - 7);
        params.start_date = d.toISOString();
      } else if (timeRange === "30d") {
        const d = new Date();
        d.setDate(d.getDate() - 30);
        params.start_date = d.toISOString();
      }

      const [ov, rev, exec, appr, fail, chan, time] = await Promise.all([
        getAnalyticsOverview(params).catch(() => null),
        getRevenueAnalytics(params).catch(() => null),
        getExecutionAnalytics(params).catch(() => null),
        getApprovalAnalytics(params).catch(() => null),
        getFailureAnalytics(params).catch(() => null),
        getChannelAnalytics(params).catch(() => []),
        getTimelineAnalytics(params).catch(() => []),
      ]);

      if (ov) setOverview(ov);
      if (rev) setRevenue(rev);
      if (exec) setExecution(exec);
      if (appr) setApprovals(appr);
      if (fail) setFailures(fail);
      if (chan) setChannels(chan);
      if (time) setTimeline(time);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load analytics");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [timeRange]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Recovery Analytics & Intelligence</h1>
          <p className="mt-1 text-sm text-slate-400">
            Performance KPIs, financial yield, channel efficiency, and error breakdown.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex rounded-lg border border-surface-border bg-surface-raised p-1">
            {[
              { id: "all", label: "All Time" },
              { id: "30d", label: "Last 30D" },
              { id: "7d", label: "Last 7D" },
              { id: "today", label: "Today" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setTimeRange(tab.id)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  timeRange === tab.id
                    ? "bg-brand-500 text-white"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <button
            onClick={() => fetchAnalytics(false)}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <span className={refreshing ? "animate-spin" : ""}>↻</span>
            {refreshing ? "..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-3.5 text-xs text-rose-300 flex items-center justify-between">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-white font-bold">✕</button>
        </div>
      )}

      {/* Financial KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Recoverable Revenue"
          value={formatRupees(revenue?.total_recoverable_amount ?? overview?.total_recoverable_amount ?? 0)}
          subValue={`${overview?.total_cases ?? 0} total cases detected`}
          accent="amber"
          icon="⚠"
        />
        <StatCard
          label="Total Recovered Revenue"
          value={formatRupees(revenue?.total_recovered_amount ?? overview?.total_recovered_amount ?? 0)}
          subValue={`${revenue?.recovered_case_count ?? overview?.recovered_cases ?? 0} cases recovered`}
          accent="emerald"
          icon="₹"
        />
        <StatCard
          label="Revenue Recovery Rate"
          value={formatPercent(revenue?.recovery_rate ?? overview?.recovery_rate ?? 0)}
          subValue={`Average recovery: ${formatRupees(revenue?.average_recovery_amount ?? 0)}`}
          accent="brand"
          icon="📈"
        />
        <StatCard
          label="Execution Success Rate"
          value={formatPercent(execution?.success_rate ?? overview?.execution_success_rate ?? 0)}
          subValue={`${execution?.succeeded ?? 0} succeeded • ${execution?.failed ?? 0} failed`}
          accent="purple"
          icon="⚡"
        />
      </div>

      {/* 30-Day Daily Recovery Timeline SVG Chart */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Recovery Trend & Time Series</h2>
            <p className="text-xs text-slate-400">Daily breakdown of created cases vs. recovered revenue</p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="h-2 w-2 rounded-full bg-brand-500"></span>
              Recoverable
            </span>
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              Recovered
            </span>
          </div>
        </div>

        {timeline.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No timeline data points for the selected date range. Seed the 30-day dataset from the Dashboard.
          </div>
        ) : (
          <div className="space-y-3">
            {/* SVG Visual Bar Chart */}
            <div className="h-48 w-full flex items-end gap-1.5 pt-6 pb-2 overflow-x-auto">
              {timeline.slice(-14).map((pt, idx) => {
                const maxVal = Math.max(...timeline.map((t) => Math.max(t.recoverable_amount, t.recovered_amount, 1)));
                const barHeight = Math.max(8, (pt.recoverable_amount / maxVal) * 120);
                const recHeight = Math.max(4, (pt.recovered_amount / maxVal) * 120);

                return (
                  <div key={idx} className="flex-1 min-w-[36px] flex flex-col items-center gap-1 group relative">
                    <div className="w-full flex items-end justify-center gap-0.5 h-[130px]">
                      {/* Recoverable bar */}
                      <div
                        className="w-2.5 rounded-t bg-brand-500/40 border border-brand-500/60 transition-all hover:bg-brand-500"
                        style={{ height: `${barHeight}px` }}
                      />
                      {/* Recovered bar */}
                      <div
                        className="w-2.5 rounded-t bg-emerald-500/80 border border-emerald-400 transition-all hover:bg-emerald-400"
                        style={{ height: `${recHeight}px` }}
                      />
                    </div>
                    <span className="text-[9px] text-slate-500 font-mono rotate-0 whitespace-nowrap">
                      {pt.date.slice(5)}
                    </span>

                    {/* Tooltip on hover */}
                    <div className="absolute bottom-full mb-2 hidden group-hover:flex flex-col rounded-lg border border-surface-border bg-slate-950 p-2 text-[10px] text-slate-200 shadow-xl z-20 whitespace-nowrap font-mono">
                      <span className="font-bold text-white">{pt.date}</span>
                      <span className="text-brand-300">At Risk: {formatRupees(pt.recoverable_amount)}</span>
                      <span className="text-emerald-400">Recovered: {formatRupees(pt.recovered_amount)}</span>
                      <span className="text-slate-400">Rate: {formatPercent(pt.recovery_rate)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Two Column Section: Channel Performance & Failure Analysis */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Channel Performance Breakdown */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-100 border-b border-surface-border pb-3">
            Communication Channel Yield
          </h2>

          <div className="space-y-3">
            {channels.map((chan) => (
              <div key={chan.channel} className="rounded-lg border border-surface-border bg-surface p-3 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <span>{chan.channel === "email" ? "✉️" : chan.channel === "sms" ? "📱" : chan.channel === "whatsapp" ? "💬" : "🔗"}</span>
                    {chan.channel}
                  </span>
                  <span className="font-bold text-emerald-400 font-mono">
                    {formatPercent(chan.success_rate)} Success
                  </span>
                </div>

                <div className="h-1.5 w-full rounded-full bg-slate-900 overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-500"
                    style={{ width: `${Math.min(100, chan.success_rate * 100)}%` }}
                  />
                </div>

                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Total Dispatches: <strong className="text-slate-200 font-mono">{chan.total}</strong></span>
                  <span>Succeeded: <strong className="text-emerald-400 font-mono">{chan.successful}</strong></span>
                  <span>Failed: <strong className="text-rose-400 font-mono">{chan.failed}</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Failure Categorization & Errors */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-100 border-b border-surface-border pb-3">
            Execution Failure Diagnostics
          </h2>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg bg-surface p-3 border border-surface-border">
              <div className="text-slate-400 text-[10px] uppercase">Total Failures</div>
              <div className="text-lg font-bold text-rose-400 mt-1 font-mono">
                {failures?.failure_count ?? 0}
              </div>
            </div>
            <div className="rounded-lg bg-surface p-3 border border-surface-border">
              <div className="text-slate-400 text-[10px] uppercase">Retryable (Backoff)</div>
              <div className="text-lg font-bold text-amber-400 mt-1 font-mono">
                {failures?.retryable_failure_count ?? 0}
              </div>
            </div>
            <div className="rounded-lg bg-surface p-3 border border-surface-border">
              <div className="text-slate-400 text-[10px] uppercase">Permanent</div>
              <div className="text-lg font-bold text-slate-300 mt-1 font-mono">
                {failures?.non_retryable_failure_count ?? 0}
              </div>
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <div className="text-xs font-medium text-slate-300">Error Code Grouping:</div>
            {failures?.error_breakdown && failures.error_breakdown.length > 0 ? (
              <div className="space-y-1.5">
                {failures.error_breakdown.map((errItem, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded bg-surface border border-surface-border text-xs font-mono">
                    <span className="text-rose-300">{errItem.error_code}</span>
                    <span className="text-slate-400 bg-slate-900 px-2 py-0.5 rounded text-[10px]">
                      {errItem.count} instances
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 py-3 text-center">No failure records detected.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
