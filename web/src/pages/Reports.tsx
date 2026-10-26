import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Button, Card, DataTable, ErrorBox, Field, Input, PageHeader, Select, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { VISIT_OUTCOMES, errorMessage, fmtDateTime } from "../lib/format";
import type { Page, ReportResult, User } from "../lib/types";

const REPORTS = [
  { key: "customers", label: "Customer directory", path: "/reports/customers", filters: ["status", "salesman"] },
  { key: "assignments", label: "Customer assignments", path: "/reports/assignments", filters: ["dates", "salesman"] },
  { key: "visits", label: "Visits", path: "/reports/visits", filters: ["dates", "salesman", "outcome"] },
  { key: "salesman-activity", label: "Salesman activity", path: "/reports/salesman-activity", filters: ["dates"] },
  { key: "followups", label: "Follow-ups (all)", path: "/reports/followups", filters: ["dates", "salesman", "fustatus"] },
  { key: "pending", label: "Pending follow-ups", path: "/reports/followups", fixed: { status: "Pending" }, filters: ["dates", "salesman"] },
  { key: "overdue", label: "Overdue follow-ups", path: "/reports/followups", fixed: { overdue: true }, filters: ["salesman"] },
  { key: "completed", label: "Completed follow-ups", path: "/reports/followups", fixed: { status: "Completed" }, filters: ["dates", "salesman"] },
  { key: "attendance", label: "Attendance & working hours", path: "/reports/attendance", filters: ["dates", "salesman"] },
  { key: "attendance-locations", label: "Attendance locations (every event)", path: "/reports/attendance-locations", filters: ["dates", "salesman"] },
  { key: "attendance-areas", label: "Attendance by area (location-wise)", path: "/reports/attendance-areas", filters: ["dates", "salesman"] },
] as const;

const looksLikeIso = (v: unknown) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}T[\d:.]+Z?$/.test(v);
const isMapLink = (v: unknown) => typeof v === "string" && v.startsWith("https://www.google.com/maps");
const cellValue = (v: unknown) =>
  isMapLink(v) ? <a href={v as string} target="_blank" rel="noreferrer" className="font-medium text-brand-600 hover:underline">Open map</a>
    : looksLikeIso(v) ? fmtDateTime(v as string) : (v as any) ?? "—";

export default function Reports() {
  const { can, me } = useAuth();
  const toast = useToast();
  const [key, setKey] = useState<string>(REPORTS[0].key);
  const [f, setF] = useState({ date_from: "", date_to: "", salesman_id: "", outcome: "", status: "", fustatus: "" });
  const [result, setResult] = useState<ReportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const report = REPORTS.find((r) => r.key === key)!;
  const showSalesman = me?.role.data_scope === "company" && can("User.View");
  const salesmen = useFetch(() => (showSalesman ? api.get<Page<User>>("/users", { scope: "assigned", page_size: 200 }) : Promise.resolve(null)), [showSalesman]);
  const has = (x: string) => (report.filters as readonly string[]).includes(x);

  const params = () => ({
    date_from: has("dates") ? f.date_from : "", date_to: has("dates") ? f.date_to : "",
    salesman_id: has("salesman") && showSalesman ? f.salesman_id : "", outcome: has("outcome") ? f.outcome : "",
    status: key === "customers" ? f.status : has("fustatus") ? f.fustatus : "", ...("fixed" in report ? report.fixed : {}),
  });

  const run = async () => {
    setLoading(true); setError(null);
    try { setResult(await api.get<ReportResult>(report.path, params())); } catch (e) { setError(errorMessage(e)); setResult(null); } finally { setLoading(false); }
  };
  const download = async () => {
    try { await api.downloadCsv(report.path, params(), `${report.key}.csv`); } catch (e) { toast(errorMessage(e), "error"); }
  };

  return (
    <>
      <PageHeader title="Reports" subtitle="Results are limited to the records you are allowed to see." />
      <Card>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Report"><Select value={key} onChange={(e) => { setKey(e.target.value); setResult(null); }}>{REPORTS.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</Select></Field>
          {has("dates") && <><Field label="From"><Input type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} /></Field>
            <Field label="To"><Input type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} /></Field></>}
          {has("salesman") && showSalesman && <Field label="Salesman"><Select value={f.salesman_id} onChange={(e) => setF({ ...f, salesman_id: e.target.value })}><option value="">All</option>{salesmen.data?.items.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}</Select></Field>}
          {has("outcome") && <Field label="Outcome"><Select value={f.outcome} onChange={(e) => setF({ ...f, outcome: e.target.value })}><option value="">All</option>{VISIT_OUTCOMES.map((o) => <option key={o}>{o}</option>)}</Select></Field>}
          {key === "customers" && <Field label="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">All</option><option>Active</option><option>Inactive</option></Select></Field>}
          {has("fustatus") && <Field label="Status"><Select value={f.fustatus} onChange={(e) => setF({ ...f, fustatus: e.target.value })}><option value="">All</option><option>Pending</option><option>Completed</option><option>Cancelled</option></Select></Field>}
        </div>
        <div className="mt-4 flex gap-2"><Button onClick={run} loading={loading}>Run report</Button><Button variant="secondary" onClick={download}>Download CSV</Button></div>
      </Card>
      <div className="mt-4">
        {error && <ErrorBox message={error} onRetry={run} />}
        {result && (
          <>
            <p className="mb-2 text-sm text-slate-600">{result.total} row(s)</p>
            <DataTable<Record<string, any>> rows={result.rows.map((r, i) => ({ ...r, __i: i }))} rowKey={(r) => r.__i} empty="No data for the selected filters."
              columns={result.columns.map((c) => ({ header: c.label, cell: (r) => cellValue(r[c.key]) }))} />
          </>
        )}
      </div>
    </>
  );
}
