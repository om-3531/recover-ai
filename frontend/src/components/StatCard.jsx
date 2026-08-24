export default function StatCard({ label, placeholder, accent = "brand" }) {
  const accentClasses = {
    brand: "text-brand-400",
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    slate: "text-slate-400",
  };

  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${accentClasses[accent]}`}>
        —
      </p>
      <p className="mt-1 text-xs text-slate-500">{placeholder}</p>
    </div>
  );
}
