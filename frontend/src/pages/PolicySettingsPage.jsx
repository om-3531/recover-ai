import { useState, useEffect } from "react";
import { getCurrentPolicy, updatePolicy, resetPolicy, previewPolicy } from "../services/api";

export default function PolicySettingsPage() {
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [errors, setErrors] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [successMessage, setSuccessMessage] = useState("");
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  // Policy preview state
  const [previewAmount, setPreviewAmount] = useState(15000);
  const [previewRisk, setPreviewRisk] = useState("high");
  const [previewResult, setPreviewResult] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  // Form state
  const [formData, setFormData] = useState({
    high_risk_threshold_rupees: 10000,
    critical_risk_threshold_rupees: 50000,
    human_review_threshold_rupees: 10000,
    auto_execute_low_risk: true,
    max_attempts: 3,
    backoff_base_seconds: 30,
    allowed_channels: ["email", "sms", "whatsapp", "webhook"],
    preferred_channel: "email",
    min_recovery_amount_rupees: 100,
    max_recovery_amount_rupees: 1000000,
    require_approval_for_high_risk: true,
    require_approval_for_critical_risk: true,
    webhook_enabled: true,
  });

  const loadPolicy = async () => {
    try {
      setLoading(true);
      const data = await getCurrentPolicy();
      setPolicy(data);
      setFormData({
        high_risk_threshold_rupees: data.high_risk_threshold_paise / 100,
        critical_risk_threshold_rupees: data.critical_risk_threshold_paise / 100,
        human_review_threshold_rupees: data.human_review_threshold_paise / 100,
        auto_execute_low_risk: data.auto_execute_low_risk,
        max_attempts: data.max_attempts,
        backoff_base_seconds: data.backoff_base_seconds,
        allowed_channels: data.allowed_channels || [],
        preferred_channel: data.preferred_channel || "email",
        min_recovery_amount_rupees: data.min_recovery_amount_paise / 100,
        max_recovery_amount_rupees: data.max_recovery_amount_paise / 100,
        require_approval_for_high_risk: data.require_approval_for_high_risk !== false,
        require_approval_for_critical_risk: data.require_approval_for_critical_risk !== false,
        webhook_enabled: data.webhook_enabled,
      });
      setErrors([]);
    } catch (err) {
      setErrors([err.message || "Failed to load policy"]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicy();
  }, []);

  const handleChannelToggle = (channel) => {
    setFormData((prev) => {
      const exists = prev.allowed_channels.includes(channel);
      const nextChannels = exists
        ? prev.allowed_channels.filter((c) => c !== channel)
        : [...prev.allowed_channels, channel];

      let nextPreferred = prev.preferred_channel;
      if (!nextChannels.includes(nextPreferred) && nextChannels.length > 0) {
        nextPreferred = nextChannels[0];
      }
      return {
        ...prev,
        allowed_channels: nextChannels,
        preferred_channel: nextPreferred,
      };
    });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!policy) return;

    setSaving(true);
    setErrors([]);
    setWarnings([]);
    setSuccessMessage("");

    const payload = {
      high_risk_threshold_paise: Math.round(formData.high_risk_threshold_rupees * 100),
      critical_risk_threshold_paise: Math.round(formData.critical_risk_threshold_rupees * 100),
      human_review_threshold_paise: Math.round(formData.human_review_threshold_rupees * 100),
      auto_execute_low_risk: formData.auto_execute_low_risk,
      max_attempts: parseInt(formData.max_attempts, 10),
      backoff_base_seconds: parseInt(formData.backoff_base_seconds, 10),
      allowed_channels: formData.allowed_channels,
      preferred_channel: formData.preferred_channel,
      min_recovery_amount_paise: Math.round(formData.min_recovery_amount_rupees * 100),
      max_recovery_amount_paise: Math.round(formData.max_recovery_amount_rupees * 100),
      require_approval_for_high_risk: formData.require_approval_for_high_risk,
      require_approval_for_critical_risk: formData.require_approval_for_critical_risk,
      webhook_enabled: formData.webhook_enabled,
    };

    try {
      const updated = await updatePolicy(policy.id, payload);
      setPolicy(updated);
      setSuccessMessage("Merchant recovery policy successfully updated and active.");
      setTimeout(() => setSuccessMessage(""), 5000);
    } catch (err) {
      setErrors([err.message || "Failed to update policy"]);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!policy) return;
    setResetting(true);
    setErrors([]);
    setSuccessMessage("");
    try {
      const resetData = await resetPolicy(policy.id);
      setPolicy(resetData);
      setFormData({
        high_risk_threshold_rupees: resetData.high_risk_threshold_paise / 100,
        critical_risk_threshold_rupees: resetData.critical_risk_threshold_paise / 100,
        human_review_threshold_rupees: resetData.human_review_threshold_paise / 100,
        auto_execute_low_risk: resetData.auto_execute_low_risk,
        max_attempts: resetData.max_attempts,
        backoff_base_seconds: resetData.backoff_base_seconds,
        allowed_channels: resetData.allowed_channels || [],
        preferred_channel: resetData.preferred_channel || "email",
        min_recovery_amount_rupees: resetData.min_recovery_amount_paise / 100,
        max_recovery_amount_rupees: resetData.max_recovery_amount_paise / 100,
        require_approval_for_high_risk: resetData.require_approval_for_high_risk !== false,
        require_approval_for_critical_risk: resetData.require_approval_for_critical_risk !== false,
        webhook_enabled: resetData.webhook_enabled,
      });
      setShowResetConfirm(false);
      setSuccessMessage("Policy reset to safe factory defaults.");
      setTimeout(() => setSuccessMessage(""), 5000);
    } catch (err) {
      setErrors([err.message || "Failed to reset policy"]);
    } finally {
      setResetting(false);
    }
  };

  const handlePreview = async () => {
    setPreviewLoading(true);
    setPreviewError("");
    setPreviewResult(null);
    try {
      const result = await previewPolicy({
        amount_paise: Math.round(previewAmount * 100),
        risk_status: previewRisk,
        channel: formData.preferred_channel || "email",
        attempt_count: 0,
        current_state: "open",
      });
      setPreviewResult(result);
    } catch (err) {
      setPreviewError(err.message || "Failed to preview policy decision");
    } finally {
      setPreviewLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          <span>Loading merchant policy configuration...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Merchant Policy & Rules Engine</h1>
          <p className="mt-1 text-sm text-slate-400">
            Define deterministic financial thresholds, automation gates, and communication constraints.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowResetConfirm(true)}
            className="rounded-lg border border-slate-700 bg-surface-raised px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          >
            Reset Defaults
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-brand-500 px-5 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50 transition-colors shadow-lg shadow-brand-500/20"
          >
            {saving ? "Saving Changes..." : "Save Policy"}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>✓</span>
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage("")} className="text-emerald-400 hover:text-emerald-200">×</button>
        </div>
      )}

      {errors.length > 0 && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300 space-y-1">
          {errors.map((err, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <span>⚠</span>
              <span>{err}</span>
            </div>
          ))}
        </div>
      )}

      {/* Live Policy Summary Banner */}
      <div className="rounded-xl border border-brand-500/30 bg-gradient-to-r from-brand-950/40 via-surface-raised to-surface-raised p-5 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-brand-500/20 p-2 text-brand-400">🛡</div>
          <div>
            <h2 className="text-sm font-semibold text-brand-300 uppercase tracking-wider">Active Policy Rules Summary</h2>
            <p className="mt-1 text-sm text-slate-200 leading-relaxed">
              {policy?.summary || "Recoveries evaluated against deterministic merchant rules before execution."}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
              <span className="rounded-full bg-slate-800/80 px-2.5 py-1 border border-slate-700">
                Merchant: <strong className="text-slate-200">{policy?.merchant_id}</strong>
              </span>
              <span className="rounded-full bg-slate-800/80 px-2.5 py-1 border border-slate-700">
                Status: <strong className="text-emerald-400">Enforced Deterministically</strong>
              </span>
              <span className="rounded-full bg-slate-800/80 px-2.5 py-1 border border-slate-700">
                AI Override: <strong className="text-rose-400">Strictly Forbidden</strong>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Settings Grid */}
      <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: Risk & Human Review Thresholds */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
          <div className="border-b border-surface-border pb-3">
            <h3 className="text-base font-semibold text-slate-100">1. Risk & Financial Review Thresholds</h3>
            <p className="text-xs text-slate-400">Set rupee amounts that govern classification and mandatory approval gates.</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300">Human Review Threshold (₹)</label>
              <p className="text-[11px] text-slate-500 mb-1">Failed payments at or above this amount strictly require supervisor approval.</p>
              <div className="relative rounded-md shadow-sm">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 text-sm">₹</span>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={formData.human_review_threshold_rupees}
                  onChange={(e) => setFormData({ ...formData, human_review_threshold_rupees: parseFloat(e.target.value) || 0 })}
                  className="w-full rounded-lg border border-surface-border bg-surface pl-8 pr-4 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300">High Risk Classification Threshold (₹)</label>
              <div className="relative rounded-md shadow-sm mt-1">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 text-sm">₹</span>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={formData.high_risk_threshold_rupees}
                  onChange={(e) => setFormData({ ...formData, high_risk_threshold_rupees: parseFloat(e.target.value) || 0 })}
                  className="w-full rounded-lg border border-surface-border bg-surface pl-8 pr-4 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300">Critical Risk Classification Threshold (₹)</label>
              <div className="relative rounded-md shadow-sm mt-1">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 text-sm">₹</span>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={formData.critical_risk_threshold_rupees}
                  onChange={(e) => setFormData({ ...formData, critical_risk_threshold_rupees: parseFloat(e.target.value) || 0 })}
                  className="w-full rounded-lg border border-surface-border bg-surface pl-8 pr-4 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Automation & Execution Controls */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
          <div className="border-b border-surface-border pb-3">
            <h3 className="text-base font-semibold text-slate-100">2. Autonomous Execution Controls</h3>
            <p className="text-xs text-slate-400">Toggle whether low-risk decisions may execute autonomously.</p>
          </div>

          <div className="space-y-4">
            <div className="flex items-start justify-between p-3 rounded-lg border border-surface-border bg-surface/50">
              <div>
                <span className="text-sm font-medium text-slate-200">Auto-Execute Low-Risk Cases</span>
                <p className="text-xs text-slate-400 mt-0.5">
                  When enabled, low-risk cases below the human review threshold will execute without waiting for manual operator clicks.
                </p>
              </div>
              <input
                type="checkbox"
                checked={formData.auto_execute_low_risk}
                onChange={(e) => setFormData({ ...formData, auto_execute_low_risk: e.target.checked })}
                className="h-5 w-5 rounded border-slate-700 bg-surface text-brand-500 focus:ring-brand-500 mt-1 cursor-pointer"
              />
            </div>

            <div className="flex items-start justify-between p-3 rounded-lg border border-surface-border bg-surface/50">
              <div>
                <span className="text-sm font-medium text-slate-200">Partner Webhook Dispatch</span>
                <p className="text-xs text-slate-400 mt-0.5">
                  Allow partner ERP / CRM notification pings as automated recovery actions.
                </p>
              </div>
              <input
                type="checkbox"
                checked={formData.webhook_enabled}
                onChange={(e) => setFormData({ ...formData, webhook_enabled: e.target.checked })}
                className="h-5 w-5 rounded border-slate-700 bg-surface text-brand-500 focus:ring-brand-500 mt-1 cursor-pointer"
              />
            </div>

            <div className="flex items-start justify-between p-3 rounded-lg border border-surface-border bg-surface/50">
              <div>
                <span className="text-sm font-medium text-slate-200">Require Approval for High Risk</span>
                <p className="text-xs text-slate-400 mt-0.5">
                  When enabled, high-risk cases (above the high-risk threshold) strictly require human supervisor approval before any execution.
                </p>
              </div>
              <input
                type="checkbox"
                checked={formData.require_approval_for_high_risk}
                onChange={(e) => setFormData({ ...formData, require_approval_for_high_risk: e.target.checked })}
                className="h-5 w-5 rounded border-slate-700 bg-surface text-brand-500 focus:ring-brand-500 mt-1 cursor-pointer"
              />
            </div>

            <div className="flex items-start justify-between p-3 rounded-lg border border-surface-border bg-surface/50">
              <div>
                <span className="text-sm font-medium text-slate-200">Require Approval for Critical Risk</span>
                <p className="text-xs text-slate-400 mt-0.5">
                  When enabled, critical-risk cases (above the critical-risk threshold) strictly require human supervisor approval before any execution.
                </p>
              </div>
              <input
                type="checkbox"
                checked={formData.require_approval_for_critical_risk}
                onChange={(e) => setFormData({ ...formData, require_approval_for_critical_risk: e.target.checked })}
                className="h-5 w-5 rounded border-slate-700 bg-surface text-brand-500 focus:ring-brand-500 mt-1 cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* Card 3: Communication Channels */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
          <div className="border-b border-surface-border pb-3">
            <h3 className="text-base font-semibold text-slate-100">3. Communication Channels</h3>
            <p className="text-xs text-slate-400">Enable or disable specific customer touchpoint channels.</p>
          </div>

          <div className="space-y-3">
            <label className="block text-xs font-medium text-slate-300">Allowed Channels</label>
            <div className="grid grid-cols-2 gap-2">
              {["email", "sms", "whatsapp", "webhook"].map((ch) => {
                const isChecked = formData.allowed_channels.includes(ch);
                return (
                  <button
                    type="button"
                    key={ch}
                    onClick={() => handleChannelToggle(ch)}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                      isChecked
                        ? "border-brand-500/50 bg-brand-500/10 text-brand-300"
                        : "border-surface-border bg-surface text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <span className="capitalize">{ch}</span>
                    <span>{isChecked ? "✓" : "×"}</span>
                  </button>
                );
              })}
            </div>

            <div className="pt-2">
              <label className="block text-xs font-medium text-slate-300">Preferred Fallback Channel</label>
              <select
                value={formData.preferred_channel}
                onChange={(e) => setFormData({ ...formData, preferred_channel: e.target.value })}
                className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
              >
                {formData.allowed_channels.map((ch) => (
                  <option key={ch} value={ch} className="capitalize">
                    {ch.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Card 4: Retry & Amount Boundaries */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
          <div className="border-b border-surface-border pb-3">
            <h3 className="text-base font-semibold text-slate-100">4. Retry Policies & Amount Bounds</h3>
            <p className="text-xs text-slate-400">Configure retry attempt caps and recoverable amount limits.</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300">Max Recovery Attempts</label>
              <input
                type="number"
                min="1"
                max="10"
                value={formData.max_attempts}
                onChange={(e) => setFormData({ ...formData, max_attempts: parseInt(e.target.value, 10) || 1 })}
                className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">Backoff Base (Seconds)</label>
              <input
                type="number"
                min="1"
                max="3600"
                value={formData.backoff_base_seconds}
                onChange={(e) => setFormData({ ...formData, backoff_base_seconds: parseInt(e.target.value, 10) || 1 })}
                className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300">Min Amount (₹)</label>
              <input
                type="number"
                min="0"
                value={formData.min_recovery_amount_rupees}
                onChange={(e) => setFormData({ ...formData, min_recovery_amount_rupees: parseFloat(e.target.value) || 0 })}
                className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">Max Amount (₹)</label>
              <input
                type="number"
                min="0"
                value={formData.max_recovery_amount_rupees}
                onChange={(e) => setFormData({ ...formData, max_recovery_amount_rupees: parseFloat(e.target.value) || 0 })}
                className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </div>
          </div>
        </div>
      </form>

      {/* Reset Confirmation Modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-surface-border bg-surface-raised p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-bold text-slate-100">Reset Policy to Defaults?</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              This will restore all risk thresholds (₹10k high risk, ₹50k critical risk, ₹10k human review), enable all 4 communication channels, and reset retry attempts to 3.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowResetConfirm(false)}
                className="rounded-lg border border-surface-border bg-surface px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleReset}
                disabled={resetting}
                className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
              >
                {resetting ? "Resetting..." : "Confirm Reset"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Policy Preview */}
      <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="border-b border-surface-border pb-3">
          <h3 className="text-base font-semibold text-slate-100">Policy Preview</h3>
          <p className="text-xs text-slate-400">
            Test what the active policy would decide for a hypothetical recovery scenario. This is purely informational and executes nothing.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-slate-300">Recovery Amount (₹)</label>
            <div className="relative rounded-md shadow-sm mt-1">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 text-sm">₹</span>
              <input
                type="number"
                min="0"
                step="100"
                value={previewAmount}
                onChange={(e) => setPreviewAmount(parseFloat(e.target.value) || 0)}
                className="w-full rounded-lg border border-surface-border bg-surface pl-8 pr-4 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300">Risk Level</label>
            <select
              value={previewRisk}
              onChange={(e) => setPreviewRisk(e.target.value)}
              className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-slate-100 focus:border-brand-500 focus:outline-none"
            >
              <option value="low">LOW</option>
              <option value="medium">MEDIUM</option>
              <option value="high">HIGH</option>
              <option value="critical">CRITICAL</option>
            </select>
          </div>

          <div>
            <button
              type="button"
              onClick={handlePreview}
              disabled={previewLoading}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {previewLoading ? "Evaluating..." : "Preview Decision"}
            </button>
          </div>
        </div>

        {previewError && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            <div className="flex items-center gap-2">
              <span>⚠</span>
              <span>{previewError}</span>
            </div>
          </div>
        )}

        {previewResult && (
          <div className={`rounded-lg border p-4 space-y-2 ${
            previewResult.evaluation.allowed && !previewResult.evaluation.requires_human_review
              ? "border-emerald-500/30 bg-emerald-500/10"
              : previewResult.evaluation.allowed && previewResult.evaluation.requires_human_review
                ? "border-amber-500/30 bg-amber-500/10"
                : "border-rose-500/30 bg-rose-500/10"
          }`}>
            <div className="flex items-center gap-2">
              <span className="text-lg">
                {!previewResult.evaluation.allowed
                  ? "🚫"
                  : previewResult.evaluation.requires_human_review
                    ? "⚠"
                    : "✓"}
              </span>
              <span className={`text-sm font-semibold ${
                !previewResult.evaluation.allowed
                  ? "text-rose-300"
                  : previewResult.evaluation.requires_human_review
                    ? "text-amber-300"
                    : "text-emerald-300"
              }`}>
                {!previewResult.evaluation.allowed
                  ? "Blocked by Policy"
                  : previewResult.evaluation.requires_human_review
                    ? "Human Approval Required"
                    : "Eligible for Automatic Recovery"}
              </span>
            </div>
            <p className="text-sm text-slate-300">{previewResult.evaluation.reason}</p>
            {previewResult.evaluation.warnings && previewResult.evaluation.warnings.length > 0 && (
              <div className="mt-2 space-y-1">
                {previewResult.evaluation.warnings.map((w, i) => (
                  <p key={i} className="text-xs text-slate-400">• {w}</p>
                ))}
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
              <span className="rounded-full bg-slate-800/80 px-2.5 py-1 border border-slate-700">
                Channel: <strong className="text-slate-200">{previewResult.evaluation.effective_channel}</strong>
              </span>
              <span className="rounded-full bg-slate-800/80 px-2.5 py-1 border border-slate-700">
                Auto-Executable: <strong className={previewResult.evaluation.is_auto_executable ? "text-emerald-400" : "text-slate-400"}>{previewResult.evaluation.is_auto_executable ? "Yes" : "No"}</strong>
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
