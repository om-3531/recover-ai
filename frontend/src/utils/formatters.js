/**
 * Currency, date, and status badge formatting helpers for RecoverAI.
 */

/**
 * Formats an integer amount in paise into INR Rupee representation.
 * e.g., 250000 -> ₹2,500.00
 */
export function formatRupees(paise, includeDecimals = true) {
  if (paise === null || paise === undefined || isNaN(paise)) return "₹0.00";
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: includeDecimals ? 2 : 0,
    maximumFractionDigits: includeDecimals ? 2 : 0,
  }).format(rupees);
}

/**
 * Formats a 0.0 - 1.0 or 0 - 100 float rate into a clean percentage string.
 */
export function formatPercent(rate) {
  if (rate === null || rate === undefined || isNaN(rate)) return "0.0%";
  const num = rate <= 1.0 && rate > 0 ? rate * 100 : rate;
  return `${num.toFixed(1)}%`;
}

/**
 * Formats an ISO date string into readable date and time.
 */
export function formatDateTime(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return String(dateStr);
    return new Intl.DateTimeFormat("en-IN", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    }).format(d);
  } catch {
    return String(dateStr);
  }
}

/**
 * Formats an ISO date string into relative time (e.g. '2m ago').
 */
export function formatRelativeTime(dateStr) {
  if (!dateStr) return "—";
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    if (isNaN(diff)) return "—";
    const secs = Math.floor(diff / 1000);
    if (secs < 30) return "just now";
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return "—";
  }
}

/**
 * Returns Tailwind badge classes for Risk Levels.
 */
export function getRiskBadge(risk) {
  const r = (risk || "").toLowerCase();
  switch (r) {
    case "critical":
      return "bg-rose-500/10 text-rose-400 border border-rose-500/30";
    case "high":
      return "bg-amber-500/10 text-amber-400 border border-amber-500/30";
    case "medium":
      return "bg-yellow-500/10 text-yellow-400 border border-yellow-500/30";
    case "low":
      return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
    default:
      return "bg-slate-500/10 text-slate-400 border border-slate-500/30";
  }
}

/**
 * Returns Tailwind badge classes for Recovery Case and Payment statuses.
 */
export function getStatusBadge(status) {
  const s = (status || "").toLowerCase();
  switch (s) {
    case "recovered":
    case "captured":
    case "approved":
    case "succeeded":
    case "operational":
    case "ready":
      return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
    case "recovering":
    case "action_pending":
    case "pending":
    case "queued":
    case "running":
    case "retry_scheduled":
      return "bg-amber-500/10 text-amber-400 border border-amber-500/30";
    case "open":
    case "at_risk":
      return "bg-indigo-500/10 text-indigo-400 border border-indigo-500/30";
    case "failed":
    case "rejected":
    case "unreachable":
    case "offline":
      return "bg-rose-500/10 text-rose-400 border border-rose-500/30";
    case "closed":
    case "cancelled":
    case "expired":
      return "bg-slate-500/10 text-slate-400 border border-slate-500/30";
    default:
      return "bg-slate-500/10 text-slate-400 border border-slate-500/30";
  }
}
