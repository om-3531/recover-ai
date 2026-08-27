import { useState, useEffect } from "react";
import { getWebhookFixtures, getWebhookTunnelGuide, sendTestWebhook } from "../services/api";

export default function WebhookConsolePage() {
  const [fixtures, setFixtures] = useState([]);
  const [selectedFixtureKey, setSelectedFixtureKey] = useState("");
  const [payloadText, setPayloadText] = useState("{}");
  const [eventType, setEventType] = useState("payment.failed");
  const [tunnelGuide, setTunnelGuide] = useState(null);
  const [activeTab, setActiveTab] = useState("console"); // console | tunnel

  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [fixturesData, guideData] = await Promise.all([
          getWebhookFixtures(),
          getWebhookTunnelGuide(),
        ]);
        setFixtures(fixturesData);
        setTunnelGuide(guideData);

        if (fixturesData.length > 0) {
          const first = fixturesData[0];
          setSelectedFixtureKey(first.key);
          setEventType(first.event_type);
          setPayloadText(JSON.stringify(first.payload, null, 2));
        }
      } catch (err) {
        setError(err.message || "Failed to load webhook console data");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleFixtureChange = (e) => {
    const key = e.target.value;
    setSelectedFixtureKey(key);
    const found = fixtures.find((f) => f.key === key);
    if (found) {
      setEventType(found.event_type);
      setPayloadText(JSON.stringify(found.payload, null, 2));
      setResponse(null);
      setError(null);
    }
  };

  const handleSendWebhook = async () => {
    try {
      setSending(true);
      setError(null);
      setResponse(null);

      let parsedPayload;
      try {
        parsedPayload = JSON.parse(payloadText);
      } catch (parseErr) {
        throw new Error(`Invalid JSON syntax in payload: ${parseErr.message}`);
      }

      const result = await sendTestWebhook(eventType, parsedPayload);
      setResponse(result);
    } catch (err) {
      setError(err.message || "Failed to execute test webhook");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          <span>Loading webhook console & tunnel recipes...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Razorpay Webhook & Tunnel Console</h1>
          <p className="mt-1 text-sm text-slate-400">
            Simulate synthetic inbound events, inspect idempotency & signatures, or configure local live tunnels.
          </p>
        </div>
        <div className="flex rounded-lg border border-surface-border bg-surface p-1">
          <button
            type="button"
            onClick={() => setActiveTab("console")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors ${
              activeTab === "console"
                ? "bg-brand-500 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            ⚡ Test Console
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("tunnel")}
            className={`rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors ${
              activeTab === "tunnel"
                ? "bg-brand-500 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            🌐 Local Tunnel Guide
          </button>
        </div>
      </div>

      {activeTab === "console" ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Event Config & JSON Editor */}
          <div className="lg:col-span-7 space-y-4">
            <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-surface-border pb-4">
                <div>
                  <h2 className="text-sm font-semibold text-slate-100">Select Synthetic Event Fixture</h2>
                  <p className="text-xs text-slate-400">Choose a predefined scenario or customize the JSON payload below.</p>
                </div>
                <select
                  value={selectedFixtureKey}
                  onChange={handleFixtureChange}
                  className="rounded-lg border border-surface-border bg-surface px-3 py-1.5 text-xs text-slate-100 focus:border-brand-500 focus:outline-none max-w-xs"
                >
                  {fixtures.map((f) => (
                    <option key={f.key} value={f.key}>
                      {f.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300">Event Type Header</label>
                  <input
                    type="text"
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value)}
                    className="rounded border border-surface-border bg-surface px-2.5 py-1 text-xs text-slate-200 font-mono"
                  />
                </div>

                <div className="relative">
                  <textarea
                    rows={16}
                    value={payloadText}
                    onChange={(e) => setPayloadText(e.target.value)}
                    className="w-full rounded-lg border border-surface-border bg-slate-950 p-3.5 font-mono text-xs text-slate-200 leading-relaxed focus:border-brand-500 focus:outline-none"
                    spellCheck="false"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-xs text-slate-500">
                  Auto-signs payload using HMAC-SHA256 test key
                </span>
                <button
                  type="button"
                  onClick={handleSendWebhook}
                  disabled={sending}
                  className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors shadow-lg shadow-emerald-600/20"
                >
                  {sending ? "Processing Webhook..." : "⚡ Dispatch Webhook"}
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Execution Response & Inspection */}
          <div className="lg:col-span-5 space-y-4">
            <div className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
              <h2 className="text-sm font-semibold text-slate-100 border-b border-surface-border pb-3">
                Webhook Processing Result
              </h2>

              {error && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300 flex items-start gap-2">
                  <span>⚠</span>
                  <span>{error}</span>
                </div>
              )}

              {response ? (
                <div className="space-y-4 text-xs">
                  {/* Status Banner */}
                  <div
                    className={`rounded-lg p-3.5 border flex items-center justify-between ${
                      response.status === "duplicate"
                        ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                        : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-base">{response.status === "duplicate" ? "♻" : "✓"}</span>
                      <div>
                        <div className="font-semibold uppercase tracking-wider text-[11px]">
                          Status: {response.status}
                        </div>
                        <div className="text-[11px] opacity-90">{response.message}</div>
                      </div>
                    </div>
                    <span className="rounded bg-black/30 px-2 py-0.5 font-mono text-[10px]">
                      HTTP 200
                    </span>
                  </div>

                  {/* Key Metadata Table */}
                  <div className="rounded-lg border border-surface-border bg-surface p-3 space-y-2 font-mono">
                    <div className="flex justify-between border-b border-surface-border pb-1.5">
                      <span className="text-slate-500">Event ID:</span>
                      <span className="text-slate-200">{response.event_id}</span>
                    </div>
                    <div className="flex justify-between border-b border-surface-border pb-1.5">
                      <span className="text-slate-500">Event Type:</span>
                      <span className="text-slate-200">{response.event_type}</span>
                    </div>
                    <div className="flex justify-between border-b border-surface-border pb-1.5">
                      <span className="text-slate-500">Idempotency:</span>
                      <span className={response.is_duplicate ? "text-amber-400" : "text-emerald-400"}>
                        {response.is_duplicate ? "DUPLICATE_IGNORED" : "FIRST_DELIVERY"}
                      </span>
                    </div>
                    <div className="flex justify-between border-b border-surface-border pb-1.5">
                      <span className="text-slate-500">Audit Action:</span>
                      <span className="text-brand-300">{response.audit_action}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Request ID:</span>
                      <span className="text-slate-400 truncate max-w-[180px]">{response.request_id}</span>
                    </div>
                  </div>

                  {/* Linked Financial & Recovery Entities */}
                  <div className="rounded-lg border border-surface-border bg-surface p-3 space-y-2">
                    <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                      Synchronized Domain Entities
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center pt-1">
                      <div className="rounded bg-surface-raised p-2 border border-surface-border">
                        <div className="text-slate-500 text-[10px]">Payment ID</div>
                        <div className="font-mono text-slate-200 font-semibold mt-0.5">
                          {response.payment_id ? `#${response.payment_id}` : "N/A"}
                        </div>
                      </div>
                      <div className="rounded bg-surface-raised p-2 border border-surface-border">
                        <div className="text-slate-500 text-[10px]">Revenue ID</div>
                        <div className="font-mono text-slate-200 font-semibold mt-0.5">
                          {response.revenue_record_id ? `#${response.revenue_record_id}` : "N/A"}
                        </div>
                      </div>
                      <div className="rounded bg-surface-raised p-2 border border-surface-border">
                        <div className="text-slate-500 text-[10px]">Case ID</div>
                        <div className="font-mono text-slate-200 font-semibold mt-0.5">
                          {response.recovery_case_id ? `#${response.recovery_case_id}` : "N/A"}
                        </div>
                      </div>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    💡 <em>Tip: Sending the same event again will safely trigger the idempotency deduplicator without creating duplicate cases or actions.</em>
                  </p>
                </div>
              ) : (
                <div className="flex h-48 flex-col items-center justify-center text-center text-slate-500 space-y-2">
                  <span className="text-2xl">📡</span>
                  <p>No webhook dispatched yet.</p>
                  <p className="text-[11px]">Select a fixture and click "Dispatch Webhook" to execute.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Tunnel Guide Tab */
        <div className="space-y-6">
          <div className="rounded-xl border border-brand-500/30 bg-gradient-to-r from-brand-950/40 via-surface-raised to-surface-raised p-5 space-y-2">
            <h2 className="text-base font-semibold text-brand-300">Connecting Real-Time Razorpay Webhooks Locally</h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              {tunnelGuide?.security_notice || "Tunnels allow Razorpay test mode webhooks to reach your local developer backend."}
            </p>
            <div className="text-xs text-slate-400 pt-1">
              Local Target Endpoint: <code className="bg-slate-900 px-2 py-0.5 rounded text-emerald-300">{tunnelGuide?.target_url}</code>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {tunnelGuide?.tunnel_options?.map((option, idx) => (
              <div key={idx} className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-3">
                <div className="flex items-center justify-between border-b border-surface-border pb-2.5">
                  <h3 className="text-sm font-bold text-slate-100">{option.tool}</h3>
                  <span className="rounded bg-brand-500/20 px-2 py-0.5 text-[10px] font-semibold text-brand-300">Recommended</span>
                </div>

                <div>
                  <div className="text-xs font-medium text-slate-400">1. Run Tunnel Command in Terminal:</div>
                  <div className="mt-1 rounded-lg bg-slate-950 p-2.5 font-mono text-xs text-emerald-400 border border-surface-border">
                    {option.command}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-medium text-slate-400">2. Configure in Razorpay Merchant Dashboard:</div>
                  <div className="mt-1 rounded-lg bg-slate-950 p-2.5 font-mono text-xs text-slate-300 border border-surface-border break-all">
                    {option.webhook_url}
                  </div>
                </div>

                <p className="text-xs text-slate-500 leading-relaxed">
                  {option.notes}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
