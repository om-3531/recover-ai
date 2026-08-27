export default function StatCard({
  label,
  value,
  subValue,
  placeholder,
  accent = "brand",
  icon,
}) {
  const accentClasses = {
    brand: "text-brand-400 border-brand-500/20 bg-brand-500/10",
    emerald: "text-emerald-400 border-emerald-500/20 bg-emerald-500/10",
    amber: "text-amber-400 border-amber-500/20 bg-amber-500/10",
    rose: "text-rose-400 border-rose-500/20 bg-rose-500/10",
    purple: "text-purple-400 border-purple-500/20 bg-purple-500/10",
    slate: "text-slate-400 border-slate-500/20 bg-slate-500/10",
  };

  const textAccent = {
    brand: "text-brand-400",
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    rose: "text-rose-400",
    purple: "text-purple-400",
    slate: "text-slate-400",
  };

  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-4 transition-all hover:border-slate-700/80">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{label}</p>
        {icon && (
          <div className={`flex h-7 w-7 items-center justify-center rounded-lg border text-sm ${accentClasses[accent]}`}>
            {icon}
          </div>
        )}
      </div>
      <p className={`mt-2 text-xl font-bold tracking-tight ${value !== undefined ? textAccent[accent] || "text-white" : "text-slate-500"}`}>
        {value !== undefined ? value : "—"}
      </p>
      {subValue ? (
        <p className="mt-0.5 text-[10px] text-slate-500 leading-snug">{subValue}</p>
      ) : placeholder ? (
        <p className="mt-0.5 text-[10px] text-slate-600">{placeholder}</p>
      ) : null}
    </div>
  );
}
