import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Badge, DataTable, Input, PageHeader, Pagination, Select } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import type { FollowUp, Page, User } from "../lib/types";

export default function FollowUps() {
  const { can, me } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [f, setF] = useState({ status: "", view: sp.get("upcoming") ? "upcoming" : sp.get("overdue") ? "overdue" : "", salesman_id: "", due_from: "", due_to: "" });
  const [page, setPage] = useState(1);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  const showSalesman = me?.role.data_scope === "company" && can("User.View");
  const params = { status: f.status, salesman_id: f.salesman_id, due_from: f.due_from, due_to: f.due_to, overdue: f.view === "overdue" || undefined, upcoming: f.view === "upcoming" || undefined, page, page_size: 25 };
  const { data, loading, error, reload } = useFetch(() => api.get<Page<FollowUp>>("/followups", params), [f.status, f.view, f.salesman_id, f.due_from, f.due_to, page]);
  const salesmen = useFetch(() => (showSalesman ? api.get<Page<User>>("/users", { scope: "assigned", page_size: 200 }) : Promise.resolve(null)), [showSalesman]);

  return (
    <>
      <PageHeader title="Follow-ups" />
      <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <Select aria-label="Status" value={f.status} onChange={set("status")}><option value="">All statuses</option><option>Pending</option><option>Completed</option><option>Cancelled</option></Select>
        <Select aria-label="View" value={f.view} onChange={set("view")}><option value="">Any due date</option><option value="overdue">Overdue</option><option value="upcoming">Upcoming</option></Select>
        {showSalesman && <Select aria-label="Salesman" value={f.salesman_id} onChange={set("salesman_id")}><option value="">All salesmen</option>{salesmen.data?.items.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}</Select>}
        <Input type="date" aria-label="Due from" value={f.due_from} onChange={set("due_from")} />
        <Input type="date" aria-label="Due to" value={f.due_to} onChange={set("due_to")} />
      </div>
      <DataTable<FollowUp> rows={data?.items} loading={loading} error={error} onRetry={reload} rowKey={(x) => x.id} onRowClick={(x) => nav(`/followups/${x.id}`)} empty="No follow-ups found."
        columns={[
          { header: "Title", cell: (x) => <span className="font-medium">{x.title}</span> }, { header: "Customer", cell: (x) => x.customer?.name },
          { header: "Due", cell: (x) => fmtDateTime(x.due_date) }, { header: "Salesman", cell: (x) => x.assigned_salesman?.full_name ?? "—" },
          { header: "Status", cell: (x) => <Badge>{x.is_overdue ? "Overdue" : x.status}</Badge> }]} />
      {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </>
  );
}
