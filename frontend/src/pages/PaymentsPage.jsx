import { useState, useEffect, useCallback } from "react";
import { listPayments } from "../services/api";
import {
  formatRupees,
  formatDateTime,
  formatRelativeTime,
  getStatusBadge,
} from "../utils/formatters";

export default function PaymentsPage() {
  const [payments, setPayments] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const fetchPayments = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const params = { limit: 100 };
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }
      const data = await listPayments(params);
      setPayments(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load payments");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  const filteredPayments = payments.filter((p) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      String(p.id).includes(q) ||
      (p.razorpay_payment_id && p.razorpay_payment_id.toLowerCase().includes(q)) ||
      (p.customer_email && p.customer_email.toLowerCase().includes(q)) ||
      (p.customer_reference && p.customer_reference.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Payment Transactions</h1>
          <p className="mt-1 text-sm text-slate-400">
            Real-time ledger of Razorpay payment transactions, failure classifications, and customer metadata.
          </p>
        </div>
        <button
          onClick={() => fetchPayments(false)}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-surface-raised px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <span className={refreshing ? "animate-spin" : ""}>↻</span>
          {refreshing ? "Refreshing..." : "Refresh Payments"}
        </button>
      </div>

      {/* Filters & Search Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-surface-border bg-surface-raised p-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-400 font-medium">Status Filter:</span>
          {["all", "failed", "captured", "created"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === st
                  ? "bg-brand-500 text-white shadow-md shadow-brand-500/20"
                  : "bg-surface text-slate-400 hover:text-slate-200 border border-surface-border"
              }`}
            >
              {st === "all" ? "All Payments" : st.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="relative min-w-[240px]">
          <input
            type="text"
            placeholder="Search payment ID, email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-surface-border bg-surface px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
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

      {/* Payment Table */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="flex items-center justify-between text-xs text-slate-400 border-b border-surface-border pb-3">
          <span>Showing {filteredPayments.length} of {total} transactions</span>
          <span className="text-[11px] text-slate-500">Amounts shown in INR (from integer paise)</span>
        </div>

        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="flex items-center gap-3 text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
              <span>Loading payment ledger...</span>
            </div>
          </div>
        ) : filteredPayments.length === 0 ? (
          <div className="py-16 text-center text-slate-500 space-y-2">
            <span className="text-3xl">💳</span>
            <p className="text-sm font-medium text-slate-400">No payments found</p>
            <p className="text-xs text-slate-500">
              {searchQuery ? "Try refining your search filter." : "Seed demo data or dispatch a webhook in Failure Lab."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-surface-border text-[10px] uppercase tracking-wider text-slate-400">
                  <th className="pb-3">Payment ID</th>
                  <th className="pb-3">Amount</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3">Method</th>
                  <th className="pb-3">Customer Email / Ref</th>
                  <th className="pb-3">Created At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50">
                {filteredPayments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3">
                      <div className="font-semibold text-slate-200">
                        #{payment.id}
                      </div>
                      <div className="font-mono text-[10px] text-slate-500">
                        {payment.razorpay_payment_id || "internal_test"}
                      </div>
                    </td>
                    <td className="py-3 font-semibold text-slate-100 whitespace-nowrap">
                      {formatRupees(payment.amount)}
                      <span className="ml-1 text-[10px] text-slate-500 font-normal">
                        {payment.currency || "INR"}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${getStatusBadge(payment.status)}`}>
                        {payment.status}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className="capitalize text-slate-300 bg-surface px-2 py-1 rounded border border-surface-border text-[11px]">
                        {payment.method || "card"}
                      </span>
                    </td>
                    <td className="py-3 text-slate-300 max-w-[200px] truncate">
                      <div>{payment.customer_email || "—"}</div>
                      {payment.customer_reference && (
                        <div className="text-[10px] text-slate-500 font-mono">
                          {payment.customer_reference}
                        </div>
                      )}
                    </td>
                    <td className="py-3 text-slate-400 whitespace-nowrap">
                      <div>{formatDateTime(payment.created_at)}</div>
                      <div className="text-[10px] text-slate-500">
                        {formatRelativeTime(payment.created_at)}
                      </div>
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
