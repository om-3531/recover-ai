import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../utils/navigation";

export default function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-60 md:flex-col border-r border-surface-border bg-surface-raised">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-surface-border">
        <div className="h-9 w-9 rounded-lg bg-brand-500 flex items-center justify-center text-base font-black text-white shadow-lg shadow-brand-500/20">
          R
        </div>
        <div>
          <span className="text-slate-100 font-bold tracking-tight text-sm">
            RecoverAI
          </span>
          <p className="text-[10px] text-slate-500 leading-tight">AI Revenue Recovery</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              [
                "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-500/15 text-brand-400 border border-brand-500/30"
                  : "text-slate-400 hover:text-slate-100 hover:bg-white/5 border border-transparent",
              ].join(" ")
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-surface-border text-[10px] text-slate-500">
        <span className="font-medium text-slate-400">Buildathon 2026</span>
        <br />
        Track 03 — AI Revenue Recovery
      </div>
    </aside>
  );
}
