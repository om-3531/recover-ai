import PlaceholderNotice from "../components/PlaceholderNotice";

export default function PlaceholderPage({ title, description }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
        <p className="text-sm text-slate-500">{description}</p>
      </div>
      <PlaceholderNotice
        title="Coming soon"
        message="This section will be implemented in a later milestone."
      />
    </div>
  );
}
