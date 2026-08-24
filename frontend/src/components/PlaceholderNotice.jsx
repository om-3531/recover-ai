export default function PlaceholderNotice({ title, message }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-surface-border bg-surface-raised/50 text-center px-6">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      <p className="mt-1 text-sm text-slate-500">{message}</p>
    </div>
  );
}
