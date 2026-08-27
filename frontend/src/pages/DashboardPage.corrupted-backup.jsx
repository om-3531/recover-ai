import StatCard from "../components/StatCard";
import PlaceholderNotice from "../components/PlaceholderNotice";
import { useSystemStatus } from "../hooks/useSystemStatus";

export default function DashboardPage() {
  const status = useSystemStatus();

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Revenue At Risk"
          placeholder="Data will appear after payment integration."
          accent="amber"
        />
        <StatCard
          label="Revenue Recovered"
          placeholder="Data will appear after payment integration."
          accent="emerald"
        />
        <StatCard
          label="Recovery Rate"
          placeholder="Data will appear after payment integration."
          accent="brand"
        />
        <StatCard
          label="Active Cases"
          placeholder="Data will appear after payment integration."
          accent="slate"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-surface-border bg-surface-raised p-5">
          <h2 className="text-sm font-medium text-slate-200">
            Recent AI Decisions
          </h2>
          <div className="mt-4">
            <PlaceholderNotice
              title="No AI decisions yet"
              message="This panel will populate once the AI recommendation engine is connected."
            />
          </div>
        </div>

        <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
          <h2 className="text-sm font-medium text-slate-200">
            System Status
          </h2>
          <ul className="mt-4 space-y-3 text-sm">
            <StatusRow
              label="Backend API"
              ok={status === "online"}
              checking={status === "checking"}
            />
            <StatusRow label="Database" ok={null} checking={false} note="Not yet connected from UI" />
            <StatusRow label="Razorpay" ok={null} checking={false} note="Not yet integrated" />
            <StatusRow label="AI Agent (Gemini)" ok={null} checking={false} note="Not yet integrated" />
          </ul>
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, ok, checking, note }) {
  let dot = "bg-slate-600";
  let text = note || "Pending";

  if (checking) {
    dot = "bg-amber-400 animate-pulse";
    text = "Checking...";
  } else if (ok === true) {
    dot = "bg-emerald-400";
    text = "Operational";
  } else if (ok === false) {
    dot = "bg-rose-400";
    text = "Unreachable";
  }

  return (
    <li className="flex items-center justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="flex items-center gap-2 text-xs text-slate-500">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        {text}
      </span>
    </li>
  );
}
