import { useState, useEffect, useCallback } from "react";
import {
  listRecoveryCases,
  generateAiDecision,
  listApprovals,
  getSystemStatus,
} from "../services/api";
import {
  formatDateTime,
  formatRelativeTime,
  getRiskBadge,
  getStatusBadge,
} from "../utils/formatters";

export default function AIDecisionsPage() {
  const [approvals, setApprovals] = useState([]);
  const [cases, setCases] = useState([]);
  const [systemStatus, setSystemStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  // Interactive Live AI Generator for Cases
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generatedResult, setGeneratedResult] = useState(null);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadData = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const [apprData, caseData, statusData] = await Promise.all([
        listApprovals({ limit: 100 }),
        listRecoveryCases({ limit: 50 }),
        getSystemStatus().catch(() => null),
      ]);
      setApprovals(apprData.items || []);
      setCases(caseData.items || []);
      if (statusData) setSystemStatus(statusData);

      if (caseData.items && caseData.items.length > 0 && !selectedCaseId) {
        setSelectedCaseId(String(caseData.items[0].id));
      }
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load AI decisions data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleGenerateDecision = async () => {
    if (!selectedCaseId) return;
    setGenerating(true);
    setError(null);
    setGeneratedResult(null);
    try {
      const res = await generateAiDecision(parseInt(selectedCaseId, 10));
      setGeneratedResult(res);
      showToast("AI decision recommendation generated.");
      await loadData(true);
    } catch (err) {
      setError(err.message || "Failed to generate AI decision");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 rounded-xl border border-emerald-500/30 bg-emerald-950/90 backdrop-blur-md px-4 py-2.5 text-xs text-emerald-200 shadow-2xl animate-fade-in flex items-center gap-2">
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">AI Recovery Decisions & Transparency</h1>
          <p className="mt-1 text-sm text-slate-400">
            Audit of AI-recommended recovery interventions, confidence probabilities, and deterministic policy boundaries.
          </p>
        </div>
        <button
          onClick={() => loadData(false)}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-surface-raised px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <span className={refreshing ? "animate-spin" : ""}>↻</span>
          {refreshing ? "Refreshing..." : "Refresh Decisions"}
        </button>
      </div>

      {/* Safety & Architecture Notice */}
      <div className="rounded-xl border border-brand-500/30 bg-gradient-to-r from-brand-950/40 via-surface-raised to-surface-raised p-5 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-brand-500/20 p-2 text-brand-400 text-lg">🛡</div>
          <div>
            <h2 className="text-sm font-semibold text-brand-300 uppercase tracking-wider">
              Safety Architecture & Human-in-the-Loop Governance
            </h2>
            <p className="mt-1 text-xs text-slate-300 leading-relaxed">
              <strong>Core Principle:</strong> AI models (Gemini / Mock) <em>only diagnose and recommend</em>. They have <strong>zero direct execution privileges</strong>. Every intervention passes through the deterministic <code>PolicyEngine</code>, creates an authoritative <code>RecoveryApproval</code> record, and mandates human supervisor sign-off for all high-risk or high-value transactions.
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400">
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">
                AI Provider: <strong className="text-emerald-400">{systemStatus?.providers_summary?.gemini ? "Gemini / Mock Safe Fallback" : "Mock / Gemini"}</strong>
              </span>
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">
                Policy Gate: <strong className="text-brand-300">Enforced Server-Side</strong>
              </span>
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">
                Direct Financial Control: <strong className="text-rose-400">Blocked</strong>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Interactive AI Decision Diagnostic Console */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-surface-border pb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Interactive AI Recommendation Tester</h2>
            <p className="text-xs text-slate-400">Select any active recovery case to generate and inspect a live AI decision payload.</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              className="rounded-lg border border-surface-border bg-surface px-3 py-1.5 text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
            >
              {cases.length === 0 ? (
                <option value="">No cases available</option>
              ) : (
                cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    Case #{c.id} — {c.reason ? c.reason.replace(/_/g, " ") : "Failure"} ({c.risk_status})
                  </option>
                ))
              )}
            </select>

            <button
              onClick={handleGenerateDecision}
              disabled={generating || !selectedCaseId}
              className="rounded-lg bg-brand-500 hover:bg-brand-600 px-4 py-1.5 text-xs font-semibold text-white transition-colors disabled:opacity-50"
            >
              {generating ? "Evaluating AI..." : "⚡ Generate Decision"}
            </button>
          </div>
        </div>

        {/* Live Generated Result Panel */}
        {generatedResult && (
          <div className="rounded-xl border border-brand-500/30 bg-surface/60 p-4 space-y-3 animate-fade-in text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-base">🤖</span>
                <span className="font-bold text-white text-sm">
                  Recommendation for Case #{generatedResult.recovery_case_id}
                </span>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                generatedResult.requires_human_review
                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                  : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              }`}>
                {generatedResult.requires_human_review ? "⚠ Human Approval Mandated" : "✓ Policy Auto-Executable"}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-[11px] pt-1">
              <div className="rounded bg-surface-raised p-2 border border-surface-border">
                <div className="text-slate-500 text-[10px]">Action Type</div>
                <div className="text-brand-300 font-semibold mt-0.5">
                  {generatedResult.recommended_action_type || "None (Blocked)"}
                </div>
              </div>
              <div className="rounded bg-surface-raised p-2 border border-surface-border">
                <div className="text-slate-500 text-[10px]">Channel</div>
                <div className="text-slate-200 font-semibold mt-0.5 capitalize">
                  {generatedResult.recommended_channel || "—"}
                </div>
              </div>
              <div className="rounded bg-surface-raised p-2 border border-surface-border">
                <div className="text-slate-500 text-[10px]">Confidence</div>
                <div className="text-emerald-400 font-semibold mt-0.5">
                  {(generatedResult.confidence * 100).toFixed(1)}%
                </div>
              </div>
              <div className="rounded bg-surface-raised p-2 border border-surface-border">
                <div className="text-slate-500 text-[10px]">Priority</div>
                <div className="text-purple-300 font-semibold mt-0.5 uppercase">
                  {generatedResult.priority}
                </div>
              </div>
            </div>

            <div className="rounded bg-surface-raised p-3 border border-surface-border space-y-1">
              <div className="text-slate-400 font-medium">Diagnosis & Rationale:</div>
              <p className="text-slate-200 leading-relaxed">{generatedResult.rationale}</p>
            </div>

            {generatedResult.risk_flags && generatedResult.risk_flags.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-slate-400 font-medium">Risk Flags:</span>
                {generatedResult.risk_flags.map((flag, idx) => (
                  <span key={idx} className="bg-rose-950/50 border border-rose-500/30 text-rose-300 px-2 py-0.5 rounded text-[10px] font-mono">
                    {flag}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-3.5 text-xs text-rose-300 flex items-center justify-between">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-white font-bold">✕</button>
        </div>
      )}

      {/* Decision Approvals Log Table */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">
              Authoritative Approval & Recommendation Records ({approvals.length})
            </h2>
            <p className="text-xs text-slate-400">Formal ledger connecting AI recommendations to merchant approvals</p>
          </div>
        </div>

        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="flex items-center gap-3 text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
              <span>Loading AI decision log...</span>
            </div>
          </div>
        ) : approvals.length === 0 ? (
          <div className="py-16 text-center text-slate-500 space-y-2">
            <span className="text-3xl">🤖</span>
            <p className="text-sm font-medium text-slate-400">No AI recommendations on record</p>
            <p className="text-xs text-slate-500">
              Generate an AI recommendation above or run a demo scenario from the Dashboard.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-surface-border text-[10px] uppercase tracking-wider text-slate-400">
                  <th className="pb-3">Approval ID</th>
                  <th className="pb-3">Case ID</th>
                  <th className="pb-3">Action Type</th>
                  <th className="pb-3">Channel</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3">Review Gate</th>
                  <th className="pb-3">Approver</th>
                  <th className="pb-3">Requested At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50">
                {approvals.map((appr) => (
                  <tr key={appr.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 font-semibold text-brand-400 font-mono">
                      #{appr.id}
                    </td>
                    <td className="py-3 font-mono text-slate-300">
                      #{appr.recovery_case_id}
                    </td>
                    <td className="py-3 font-medium text-slate-200">
                      {appr.action_type ? appr.action_type.replace(/_/g, " ") : "Payment Link"}
                    </td>
                    <td className="py-3 capitalize text-slate-300">
                      <span className="bg-surface px-2 py-0.5 rounded border border-surface-border">
                        {appr.channel}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold capitalize ${getStatusBadge(appr.status)}`}>
                        {appr.status}
                      </span>
                    </td>
                    <td className="py-3">
                      {appr.requires_human_review ? (
                        <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 border border-rose-500/30 px-1.5 py-0.5 text-[10px] font-semibold text-rose-400">
                          Human Review
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400">
                          Auto-Approved
                        </span>
                      )}
                    </td>
                    <td className="py-3 font-mono text-slate-400 text-[11px]">
                      {appr.approved_by || "—"}
                    </td>
                    <td className="py-3 text-slate-400 whitespace-nowrap">
                      {formatRelativeTime(appr.requested_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
