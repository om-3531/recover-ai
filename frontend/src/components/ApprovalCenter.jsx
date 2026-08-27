import { useState, useEffect, useCallback } from "react";
import { listApprovals, approveApproval, rejectApproval, executeApproval } from "../services/api";

/**
 * ApprovalCenter — Human-in-the-loop approval dashboard widget.
 *
 * Shows pending recovery approvals with Approve/Reject buttons.
 * Judges interact with this to demonstrate the "AI recommends → Human approves" flow.
 */
export default function ApprovalCenter({ onApprovalAction }) {
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionInProgress, setActionInProgress] = useState(null);
  const [rejectReason, setRejectReason] = useState({});
  const [showRejectInput, setShowRejectInput] = useState({});

  const fetchPending = useCallback(async () => {
    try {
      const res = await listApprovals({ status: "pending", limit: 50 });
      setPendingApprovals(res.items || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPending();
    const interval = setInterval(fetchPending, 5000);
    return () => clearInterval(interval);
  }, [fetchPending]);

  const handleApprove = async (approvalId) => {
    setActionInProgress(approvalId);
    try {
      await approveApproval(approvalId, "dashboard_operator");
      try {
        await executeApproval(approvalId);
      } catch (execErr) {
        setError(`Approved, but execution failed: ${execErr.message}`);
        await fetchPending();
        if (onApprovalAction) onApprovalAction(approvalId, "approved");
        return;
      }
      await fetchPending();
      if (onApprovalAction) onApprovalAction(approvalId, "approved");
    } catch (err) {
      setError(`Approval failed: ${err.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleReject = async (approvalId) => {
    setActionInProgress(approvalId);
    try {
      const reason = rejectReason[approvalId] || "Rejected from dashboard";
      await rejectApproval(approvalId, reason, "dashboard_operator");
      setRejectReason((prev) => ({ ...prev, [approvalId]: "" }));
      setShowRejectInput((prev) => ({ ...prev, [approvalId]: false }));
      await fetchPending();
      if (onApprovalAction) onApprovalAction(approvalId, "rejected");
    } catch (err) {
      setError(`Rejection failed: ${err.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  const toggleRejectInput = (approvalId) => {
    setShowRejectInput((prev) => ({ ...prev, [approvalId]: !prev[approvalId] }));
  };

  if (loading && pendingApprovals.length === 0) {
    return (
      <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-r from-amber-950/30 via-surface-card to-orange-950/20 p-4 backdrop-blur-md">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-400 font-bold text-lg shadow-inner">
            🛡
          </div>
          <div>
            <span className="text-sm font-semibold text-white tracking-tight">
              Approval Center
            </span>
            <p className="text-xs text-slate-400 mt-0.5">Loading pending approvals...</p>
          </div>
        </div>
        <div className="py-6 text-center text-[11px] text-amber-400/70 animate-pulse">
          Checking for pending approvals...
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-r from-amber-950/30 via-surface-card to-orange-950/20 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-400 font-bold text-lg shadow-inner">
            🛡
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white tracking-tight">
                Approval Center
              </span>
              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold border ${
                pendingApprovals.length > 0
                  ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${
                  pendingApprovals.length > 0 ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
                }`}></span>
                {pendingApprovals.length} Pending
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Human-in-the-loop: AI recommends, you decide. No action executes without your approval.
            </p>
          </div>
        </div>
        <button
          onClick={fetchPending}
          className="rounded-lg bg-slate-800/50 border border-slate-700/50 px-2.5 py-1.5 text-[11px] font-medium text-slate-400 hover:text-white transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-lg border border-rose-500/20 bg-rose-950/30 p-2 text-[11px] text-rose-300">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-rose-400 hover:text-white font-bold">✕</button>
        </div>
      )}

      {pendingApprovals.length === 0 ? (
        <div className="py-8 text-center">
          <div className="text-2xl mb-2">✅</div>
          <p className="text-[11px] text-emerald-400/80 font-medium">No pending approvals</p>
          <p className="text-[10px] text-slate-500 mt-1">
            All recovery actions are either approved, rejected, or auto-executed.
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Click "High-Risk (Approval Required)" in the demo controls above to generate one.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {pendingApprovals.map((appr) => (
            <ApprovalRow
              key={appr.id}
              approval={appr}
              isProcessing={actionInProgress === appr.id}
              showReject={showRejectInput[appr.id]}
              rejectReasonValue={rejectReason[appr.id] || ""}
              onApprove={() => handleApprove(appr.id)}
              onReject={() => handleReject(appr.id)}
              onToggleReject={() => toggleRejectInput(appr.id)}
              onRejectReasonChange={(val) =>
                setRejectReason((prev) => ({ ...prev, [appr.id]: val }))
              }
            />
          ))}
        </div>
      )}

      {/* Safety notice */}
      <div className="mt-3 flex items-center gap-2 rounded-xl border border-amber-500/10 bg-amber-950/20 px-3 py-2 text-[10px] text-amber-300/70">
        <span className="shrink-0">🔒</span>
        <span>
          Demo mode — approving/rejecting uses mock providers. No real money is moved.
          All decisions are logged for audit compliance.
        </span>
      </div>
    </div>
  );
}

/**
 * Individual approval row with approve/reject actions.
 */
function ApprovalRow({
  approval,
  isProcessing,
  showReject,
  rejectReasonValue,
  onApprove,
  onReject,
  onToggleReject,
  onRejectReasonChange,
}) {
  const actionLabels = {
    payment_link: "Payment Link",
    email_reminder: "Email Reminder",
    sms_reminder: "SMS Reminder",
    whatsapp_message: "WhatsApp Message",
    webhook_ping: "Webhook Ping",
    in_app_notification: "In-App Notification",
  };

  const channelIcons = {
    email: "✉️",
    sms: "📱",
    whatsapp: "💬",
    webhook: "🔗",
    in_app: "🔔",
  };

  const timeSince = (dateStr) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    return `${hrs}h ${mins % 60}m ago`;
  };

  return (
    <div className="rounded-xl border border-amber-500/15 bg-amber-950/15 p-3 transition-colors hover:border-amber-500/25">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-semibold text-amber-300">
              Approval #{approval.id}
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium text-amber-400">
              <span className="h-1 w-1 rounded-full bg-amber-400 animate-pulse"></span>
              Pending
            </span>
            <span className="text-[10px] text-slate-500">
              Case #{approval.recovery_case_id}
            </span>
          </div>
          <div className="mt-1.5 flex items-center gap-3 text-[11px] text-slate-400">
            <span className="flex items-center gap-1">
              <span>{channelIcons[approval.channel] || "⚙️"}</span>
              {approval.channel}
            </span>
            <span>{actionLabels[approval.action_type] || approval.action_type}</span>
            {approval.requires_human_review && (
              <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.5 text-[10px] font-medium text-rose-400">
                High Risk
              </span>
            )}
            <span className="text-slate-600">
              {timeSince(approval.requested_at)}
            </span>
          </div>
          {approval.recommendation_id && (
            <div className="mt-1 text-[10px] text-slate-600 font-mono">
              rec: {approval.recommendation_id}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={onApprove}
            disabled={isProcessing}
            className="inline-flex items-center gap-1 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-500 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm hover:from-emerald-700 hover:to-teal-600 transition-all disabled:opacity-50"
          >
            {isProcessing ? (
              <span className="animate-pulse">...</span>
            ) : (
              <>✓ Approve</>
            )}
          </button>
          <button
            onClick={onToggleReject}
            disabled={isProcessing}
            className="inline-flex items-center gap-1 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-[11px] font-semibold text-rose-400 hover:bg-rose-500/20 transition-all disabled:opacity-50"
          >
            ✕ Reject
          </button>
        </div>
      </div>

      {/* Rejection Reason Input */}
      {showReject && (
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text"
            placeholder="Rejection reason (optional)"
            value={rejectReasonValue}
            onChange={(e) => onRejectReasonChange(e.target.value)}
            className="flex-1 rounded-lg border border-rose-500/20 bg-rose-950/20 px-2.5 py-1.5 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-rose-500/40"
          />
          <button
            onClick={onReject}
            disabled={isProcessing}
            className="inline-flex items-center gap-1 rounded-lg bg-rose-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-rose-700 transition-all disabled:opacity-50"
          >
            Confirm Reject
          </button>
          <button
            onClick={onToggleReject}
            className="rounded-lg border border-slate-600 px-2 py-1.5 text-[10px] text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
