import Sidebar from "../components/Sidebar";
import TopNav from "../components/TopNav";

export default function DashboardLayout({ children }) {
  return (
    <div className="flex h-screen bg-surface">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-y-auto px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
