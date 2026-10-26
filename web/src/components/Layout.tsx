import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Icon, IconName } from "./icons";

interface NavItem { to: string; label: string; icon: IconName; show: boolean }

export default function Layout() {
  const { me, can, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  if (!me) return null;

  const main: NavItem[] = [
    { to: "/", label: "Dashboard", icon: "dashboard", show: true },
    { to: "/customers", label: "Customers", icon: "customers", show: can("Customer.View") },
    { to: "/visits", label: "Visits", icon: "visits", show: can("Visit.View") },
    { to: "/followups", label: "Follow-ups", icon: "followups", show: can("FollowUp.View") },
    { to: "/attendance", label: "Attendance", icon: "attendance", show: can("Attendance.View") && me.role.data_scope === "company" },
    { to: "/reports", label: "Reports", icon: "reports", show: can("Reports.View") },
  ];
  const admin: NavItem[] = [
    { to: "/users", label: "Users", icon: "users", show: can("User.View") },
    { to: "/roles", label: "Roles & permissions", icon: "roles", show: can("User.View") && can("Company.Edit") },
    { to: "/branches", label: "Branches", icon: "branches", show: can("Branch.Create") || can("Branch.Edit") },
    { to: "/company", label: "Company", icon: "company", show: can("Company.Edit") },
    { to: "/profile", label: "My profile", icon: "profile", show: true },
  ];

  const link = ({ isActive }: { isActive: boolean }) =>
    `group flex items-center gap-3 rounded-lg px-3 py-[7px] text-sm font-medium transition ${
      isActive ? "bg-white/10 text-white shadow-[inset_2px_0_0_0_#6da7ec]" : "text-slate-400 hover:bg-white/5 hover:text-slate-100"}`;

  const section = (title: string, items: NavItem[]) => {
    const visible = items.filter((i) => i.show);
    if (!visible.length) return null;
    return (
      <div>
        <div className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{title}</div>
        <div className="space-y-0.5">
          {visible.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/"} className={link} onClick={() => setOpen(false)}>
              <Icon name={i.icon} className="shrink-0 opacity-90" />{i.label}
            </NavLink>
          ))}
        </div>
      </div>
    );
  };

  const initials = me.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const Logo = (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-lg shadow-brand-900/30">
        <Icon name="target" size={18} />
      </span>
      <span className="text-[17px] font-semibold tracking-tight text-white">FieldSales</span>
    </Link>
  );

  return (
    <div className="min-h-screen bg-[#f6f7f9] md:flex">
      <header className="sticky top-0 z-30 flex items-center justify-between bg-slate-950 px-4 py-3 md:hidden">
        {Logo}
        <button aria-label="Toggle menu" aria-expanded={open} className="rounded-lg p-2 text-slate-300 hover:bg-white/10" onClick={() => setOpen((o) => !o)}>
          <Icon name={open ? "x" : "menu"} size={20} />
        </button>
      </header>
      <aside className={`${open ? "flex" : "hidden"} flex-col bg-slate-950 px-3 pb-3 pt-4 md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0`}>
        <div className="mb-5 hidden px-3 pt-1 md:block">{Logo}</div>
        {/* menu scrolls only when the window is very short; the scrollbar stays hidden until hovered */}
        <nav aria-label="Main" className="sidebar-scroll -mr-1 min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
          {section("Workspace", main)}
          {section("Administration", admin)}
        </nav>
        <div className="mt-3 flex items-center gap-3 border-t border-white/10 px-2 pt-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-500/20 text-sm font-semibold text-brand-300">{initials}</span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-white">{me.full_name}</div>
            <div className="truncate text-xs text-slate-400">{me.role.name} · {me.company_name}</div>
          </div>
          <button aria-label="Log out" title="Log out"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-white/10 hover:text-white"
            onClick={async () => { await logout(); nav("/login"); }}>
            <Icon name="logout" size={16} />
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-8"><Outlet /></main>
    </div>
  );
}
