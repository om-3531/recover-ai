import { useSystemStatus } from "../hooks/useSystemStatus";

const STATUS_STYLES = {
  online: { dot: "bg-emerald-400", label: "Backend online" },
  offline: { dot: "bg-rose-400", label: "Backend offline" },
  checking: { dot: "bg-amber-400 animate-pulse", label: "Checking backend..." },
};

export default function TopNav() {
  const status = useSystemStatus();
  const style = STATUS_STYLES[status];

  return (
    <header className="flex items-center justify-between border-b border-surface-border bg-surface/80 backdrop-blur px-6 py-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Dashboard</h1>
        <p className="text-sm text-slate-500">
          Revenue recovery overview for RecoverAI
        </p>
      </div>

      <div className="flex items-center gap-2 rounded-full border border-surface-border bg-surface-raised px-3 py-1.5 text-xs text-slate-300">
        <span className={`h-2 w-2 rounded-full ${style.dot}`} />
        {style.label}
      </div>
    </header>
  );
}
