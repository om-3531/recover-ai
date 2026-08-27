import { useSystemStatus } from "../hooks/useSystemStatus";

const STATUS_STYLES = {
  online: { dot: "bg-emerald-400", label: "Backend Online" },
  offline: { dot: "bg-rose-400", label: "Backend Offline" },
  checking: { dot: "bg-amber-400 animate-pulse", label: "Checking..." },
};

export default function TopNav() {
  const status = useSystemStatus();
  const style = STATUS_STYLES[status];

  return (
    <header className="flex items-center justify-between border-b border-surface-border bg-surface/80 backdrop-blur px-6 py-3">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-200">Dashboard</h2>
        <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20">
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse"></span>
          Demo Mode
        </span>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 rounded-full border border-surface-border bg-surface-raised px-3 py-1 text-[11px] text-slate-300">
          <span className={`h-2 w-2 rounded-full ${style.dot}`} />
          {style.label}
        </div>
      </div>
    </header>
  );
}
