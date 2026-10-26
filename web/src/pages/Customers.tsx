import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, DataTable, Input, PageHeader, Pagination, Select } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { BUSINESS_TYPES } from "../lib/format";
import type { Customer, Page, User } from "../lib/types";

export default function Customers() {
  const { can, me } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ q: "", status: "", business_type: "", salesman_id: "", unassigned: "" });
  const [page, setPage] = useState(1);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  const showSalesmanFilters = !!me && me.role.data_scope === "company" && can("User.View");

  const { data, loading, error, reload } = useFetch(
    () => api.get<Page<Customer>>("/customers", { ...f, unassigned: f.unassigned || undefined, page, page_size: 25 }),
    [f.q, f.status, f.business_type, f.salesman_id, f.unassigned, page],
  );
  const salesmen = useFetch(() => (showSalesmanFilters ? api.get<Page<User>>("/users", { scope: "assigned", page_size: 200 }) : Promise.resolve(null)), [showSalesmanFilters]);

  return (
    <>
      <PageHeader title="Customers" actions={can("Customer.Create") && <Link to="/customers/new"><Button>New customer</Button></Link>} />
      <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <Input placeholder="Search name, mobile, city…" aria-label="Search" value={f.q} onChange={set("q")} />
        <Select aria-label="Status" value={f.status} onChange={set("status")}><option value="">All statuses</option><option>Active</option><option>Inactive</option></Select>
        <Select aria-label="Business type" value={f.business_type} onChange={set("business_type")}><option value="">All business types</option>{BUSINESS_TYPES.map((b) => <option key={b}>{b}</option>)}</Select>
        {showSalesmanFilters && (
          <Select aria-label="Salesman" value={f.salesman_id} onChange={set("salesman_id")}>
            <option value="">All salesmen</option>{salesmen.data?.items.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
          </Select>
        )}
        {showSalesmanFilters && (
          <Select aria-label="Assignment" value={f.unassigned} onChange={set("unassigned")}><option value="">Assigned & unassigned</option><option value="true">Unassigned only</option></Select>
        )}
      </div>
      <DataTable<Customer> rows={data?.items} loading={loading} error={error} onRetry={reload} rowKey={(c) => c.id} onRowClick={(c) => nav(`/customers/${c.id}`)}
        empty="No customers match your filters."
        columns={[
          { header: "Name", cell: (c) => <span className="font-medium">{c.name}</span> },
          { header: "Mobile", cell: (c) => c.mobile },
          { header: "City", cell: (c) => c.city },
          { header: "Business", cell: (c) => c.business_type ?? "—" },
          { header: "Salesman", cell: (c) => c.assigned_salesman?.full_name ?? <span className="text-slate-400">Unassigned</span> },
          { header: "Status", cell: (c) => <Badge>{c.status}</Badge> },
        ]} />
      {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </>
  );
}
