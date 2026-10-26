import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Badge, Card, DataTable, ErrorBox, Loading, PageHeader, StatCard } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import type { Dashboard as Dash, FollowUp } from "../lib/types";

export default function Dashboard() {
  const { me } = useAuth();
  const tz = -new Date().getTimezoneOffset();
  const { data: d, loading, error, reload } = useFetch(() => api.get<Dash>("/dashboard", { tz_offset_minutes: tz }), [tz]);
  if (loading && !d) return <Loading />;
  if (error || !d) return <ErrorBox message={error ?? "No data"} onRetry={reload} />;
  const company = d.kind !== "salesman";

  return (
    <>
      <PageHeader title={`Welcome, ${me?.full_name}`} subtitle={`${d.kind === "admin" ? "Administrator" : d.kind === "manager" ? "Manager" : "Salesman"} dashboard`} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {company ? (<>
          <StatCard label="Total customers" value={d.total_customers} />
          <StatCard label="Active customers" value={d.active_customers} />
          <StatCard label="Salesmen" value={d.total_salesmen} />
          <StatCard label="Unassigned customers" value={d.assignment_summary.unassigned_customers} tone={d.assignment_summary.unassigned_customers ? "warn" : undefined} />
        </>) : (<>
          <StatCard label="Assigned customers" value={d.assigned_customers} />
          <StatCard label="Created by me (visible)" value={d.created_by_me_visible} />
        </>)}
        <StatCard label="Total visits" value={d.total_visits} />
        <StatCard label="Today's visits" value={d.todays_visits} />
        <StatCard label="Pending follow-ups" value={d.pending_followups} />
        <StatCard label="Overdue follow-ups" value={d.overdue_followups} tone={d.overdue_followups ? "danger" : undefined} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title="Upcoming follow-ups" actions={<Link className="text-sm text-brand-600" to="/followups?upcoming=true">View all</Link>}>
          <DataTable<FollowUp> rows={d.upcoming_followups} rowKey={(f) => f.id} empty="No upcoming follow-ups."
            columns={[
              { header: "Follow-up", cell: (f) => <Link className="text-brand-600 hover:underline" to={`/followups/${f.id}`}>{f.title}</Link> },
              { header: "Due", cell: (f) => fmtDateTime(f.due_date) },
              { header: "Salesman", cell: (f) => f.assigned_salesman?.full_name ?? "—" },
            ]} />
        </Card>
        <Card title="Recent visits">
          <DataTable<any> rows={d.recent_visits} rowKey={(v) => v.id} empty="No visits recorded yet."
            columns={[
              { header: "Customer", cell: (v) => <Link className="text-brand-600 hover:underline" to={`/visits/${v.id}`}>{v.customer_name}</Link> },
              { header: "When", cell: (v) => fmtDateTime(v.visit_time) },
              { header: "By", cell: (v) => v.user_name },
              { header: "Outcome", cell: (v) => v.outcome ?? "—" },
            ]} />
        </Card>

        {company ? (<>
          <Card title="Salesman activity" className="lg:col-span-2">
            <DataTable<any> rows={d.salesman_summaries} rowKey={(s) => s.salesman_id} empty="No salesmen yet."
              columns={[
                { header: "Salesman", cell: (s) => s.salesman_name },
                { header: "Customers", cell: (s) => s.assigned_customers },
                { header: "Visits (total)", cell: (s) => s.total_visits },
                { header: "Visits today", cell: (s) => s.todays_visits },
                { header: "Pending", cell: (s) => s.pending_followups },
                { header: "Overdue", cell: (s) => (s.overdue_followups ? <Badge>Overdue</Badge> : 0) },
              ]} />
          </Card>
          <Card title="Recently visited customers">
            <DataTable<any> rows={d.recently_visited_customers} rowKey={(c) => c.id} empty="No visited customers yet."
              columns={[
                { header: "Customer", cell: (c) => <Link className="text-brand-600 hover:underline" to={`/customers/${c.id}`}>{c.name}</Link> },
                { header: "City", cell: (c) => c.city },
                { header: "Last visit", cell: (c) => fmtDateTime(c.last_visit) },
              ]} />
          </Card>
        </>) : (
          <Card title="Recent customer interactions">
            <DataTable<any> rows={d.recent_interactions} rowKey={(o) => `${o.follow_up_id}-${o.recorded_at}`} empty="No interactions recorded yet."
              columns={[
                { header: "Customer", cell: (o) => o.customer_name },
                { header: "Outcome", cell: (o) => <Link className="text-brand-600 hover:underline" to={`/followups/${o.follow_up_id}`}>{o.outcome_text}</Link> },
                { header: "When", cell: (o) => fmtDateTime(o.recorded_at) },
              ]} />
          </Card>
        )}
      </div>
    </>
  );
}
