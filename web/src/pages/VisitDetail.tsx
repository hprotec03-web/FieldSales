import { Link, useParams } from "react-router-dom";
import { Card, ErrorBox, Loading, PageHeader } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import type { Visit } from "../lib/types";
import { PrivateImage } from "./PrivateImage";

export default function VisitDetail() {
  const { id } = useParams();
  const { data: v, loading, error, reload } = useFetch(() => api.get<Visit>(`/visits/${id}`), [id]);
  if (loading && !v) return <Loading />;
  if (error || !v) return <ErrorBox message={error ?? "Visit not found"} onRetry={reload} />;
  const rows: [string, React.ReactNode][] = [
    ["Customer", <Link key="c" className="text-brand-600 hover:underline" to={`/customers/${v.customer_id}`}>{v.customer_name}</Link>],
    ["Salesman", v.user_name], ["When", fmtDateTime(v.visit_time)], ["Branch", v.branch_name], ["Purpose", v.purpose], ["Outcome", v.outcome], ["Notes", v.notes],
    ["Location", v.latitude != null && v.longitude != null ? <a key="m" className="text-brand-600 hover:underline" target="_blank" rel="noopener noreferrer" href={`https://www.google.com/maps?q=${v.latitude},${v.longitude}`}>{v.latitude}, {v.longitude}</a> : "Not captured"],
    ["Follow-up", v.follow_up_id ? <Link key="f" className="text-brand-600 hover:underline" to={`/followups/${v.follow_up_id}`}>Open follow-up</Link> : "None"],
  ];
  return (
    <>
      <PageHeader title={`Visit #${v.id}`} subtitle={v.customer_name ?? ""} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Details" className="lg:col-span-2">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">{rows.map(([k, val]) => <div key={k}><dt className="text-xs uppercase text-slate-500">{k}</dt><dd>{val || "—"}</dd></div>)}</dl>
        </Card>
        <Card title="Visit photo">{v.photo_url ? <PrivateImage path={v.photo_url} /> : <p className="text-sm text-slate-500">No photo.</p>}</Card>
      </div>
    </>
  );
}
