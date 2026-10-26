import { ReactNode, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

interface NavItem { to: string; label: string; show: boolean }

export default function Layout() {
  const { me, can, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  if (!me) return null;

  const items: NavItem[] = [
    { to: "/", label: "Dashboard", show: true },
    { to: "/customers", label: "Customers", show: can("Customer.View") },
    { to: "/visits", label: "Visits", show: can("Visit.View") },
    { to: "/followups", label: "Follow-ups", show: can("FollowUp.View") },
    { to: "/reports", label: "Reports", show: can("Reports.View") },
    { to: "/users", label: "Users", show: can("User.View") },
    { to: "/roles", label: "Roles & permissions", show: can("User.View") && can("Company.Edit") },
    { to: "/branches", label: "Branches", show: can("Branch.Create") || can("Branch.Edit") },
    { to: "/company", label: "Company", show: can("Company.Edit") },
    { to: "/profile", label: "My profile", show: true },
  ];

  const link = ({ isActive }: { isActive: boolean }) =>
    `block rounded-md px-3 py-2 text-sm ${isActive ? "bg-brand-50 font-semibold text-brand-700" : "text-slate-600 hover:bg-slate-100"}`;

  const sidebar: ReactNode = (
    <nav aria-label="Main" className="space-y-1">
      {items.filter((i) => i.show).map((i) => (
        <NavLink key={i.to} to={i.to} end={i.to === "/"} className={link} onClick={() => setOpen(false)}>{i.label}</NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen md:flex">
      <header className="flex items-center justify-between border-b bg-white px-4 py-3 md:hidden">
        <Link to="/" className="font-bold text-brand-600">FieldSales</Link>
        <button aria-label="Toggle menu" className="rounded-md border px-3 py-1 text-sm" onClick={() => setOpen((o) => !o)}>Menu</button>
      </header>
      <aside className={`${open ? "block" : "hidden"} border-r bg-white p-4 md:block md:w-60 md:shrink-0`}>
        <Link to="/" className="mb-4 hidden text-lg font-bold text-brand-600 md:block">FieldSales</Link>
        {sidebar}
        <div className="mt-6 border-t pt-4 text-xs text-slate-500">
          <div className="font-medium text-slate-700">{me.full_name}</div>
          <div>{me.role.name} · {me.company_name}</div>
          <button className="mt-2 text-red-600 hover:underline" onClick={async () => { await logout(); nav("/login"); }}>Log out</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-6"><Outlet /></main>
    </div>
  );
}
