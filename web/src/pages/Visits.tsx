import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Button, DataTable, Input, PageHeader, Pagination, Select } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { VISIT_OUTCOMES, fmtDateTime } from "../lib/format";
import type { Page, User, Visit } from "../lib/types";

export default function Visits() {
  const { can, me } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [f, setF] = useState({ customer_id: sp.get("customer_id") ?? "", salesman_id: "", outcome: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  const showSalesman = me?.role.data_scope === "company" && can("User.View");
  const { data, loading, error, reload } = useFetch(() => api.get<Page<Visit>>("/visits", { ...f, page, page_size: 25 }), [f.customer_id, f.salesman_id, f.outcome, f.date_from, f.date_to, page]);
  const salesmen = useFetch(() => (showSalesman ? api.get<Page<User>>("/users", { scope: "assigned", page_size: 200 }) : Promise.resolve(null)), [showSalesman]);

  return (
    <>
      <PageHeader title="Visits" actions={can("Visit.Create") && <Link to="/visits/new"><Button>Record visit</Button></Link>} />
      {f.customer_id && <p className="mb-2 text-sm text-slate-600">Filtered by customer #{f.customer_id} <button className="text-brand-600 underline" onClick={() => setF({ ...f, customer_id: "" })}>clear</button></p>}
      <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {showSalesman && <Select aria-label="Salesman" value={f.salesman_id} onChange={set("salesman_id")}><option value="">All salesmen</option>{salesmen.data?.items.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}</Select>}
        <Select aria-label="Outcome" value={f.outcome} onChange={set("outcome")}><option value="">All outcomes</option>{VISIT_OUTCOMES.map((o) => <option key={o}>{o}</option>)}</Select>
        <Input type="date" aria-label="From date" value={f.date_from} onChange={set("date_from")} />
        <Input type="date" aria-label="To date" value={f.date_to} onChange={set("date_to")} />
      </div>
      <DataTable<Visit> rows={data?.items} loading={loading} error={error} onRetry={reload} rowKey={(v) => v.id} onRowClick={(v) => nav(`/visits/${v.id}`)} empty="No visits found."
        columns={[
          { header: "When", cell: (v) => fmtDateTime(v.visit_time) }, { header: "Customer", cell: (v) => <span className="font-medium">{v.customer_name}</span> },
          { header: "Salesman", cell: (v) => v.user_name }, { header: "Purpose", cell: (v) => v.purpose ?? "—" }, { header: "Outcome", cell: (v) => v.outcome ?? "—" },
          { header: "Follow-up", cell: (v) => (v.follow_up_id ? "Yes" : "—") }]} />
      {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
    </>
  );
}
