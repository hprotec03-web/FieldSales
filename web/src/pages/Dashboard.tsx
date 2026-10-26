import { ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ColumnChart, HBarChart, Meter, MiniTable, Segment, Sparkline, StackedBar, STATUS, ViewToggle, compact } from "../components/charts";
import { Icon, IconName } from "../components/icons";
import { ErrorBox, Loading } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import type { Dashboard as Dash, FollowUp } from "../lib/types";

interface TrendPoint { date: string; visits: number }
interface OutcomeRow { outcome: string; visits: number }
interface SalesmanRow { salesman_id: number; salesman_name: string; assigned_customers: number; total_visits: number; todays_visits: number; pending_followups: number; overdue_followups: number }
type View = "chart" | "table";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

/* ---------- layout pieces ---------- */
function Panel({ title, subtitle, actions, children, className }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("min-w-0 rounded-2xl border border-slate-200/70 bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]", className)}>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {actions}
      </header>
      {children}
    </section>
  );
}

function Kpi({ icon, label, value, sub, tone = "brand", children }: {
  icon: IconName; label: string; value: number; sub?: ReactNode; tone?: "brand" | "critical" | "warning" | "good"; children?: ReactNode;
}) {
  const chip = { brand: "bg-brand-50 text-brand-600", critical: "bg-red-50 text-red-600", warning: "bg-amber-50 text-amber-600", good: "bg-green-50 text-green-700" }[tone];
  return (
    <div className="flex min-w-0 flex-col justify-between rounded-2xl border border-slate-200/70 bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
      <div className="flex items-center gap-3">
        <span className={cx("flex h-9 w-9 items-center justify-center rounded-xl", chip)}><Icon name={icon} /></span>
        <span className="text-sm font-medium text-slate-600">{label}</span>
      </div>
      <div className="mt-4 flex items-end justify-between gap-2">
        <div>
          <div className="text-3xl font-semibold tracking-tight text-slate-900">{compact(value)}</div>
          {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
        </div>
        {children}
      </div>
    </div>
  );
}

function Delta({ now, before, period }: { now: number; before: number; period: string }) {
  if (!before) return <span className="text-slate-500">{period}</span>;
  const pct = Math.round(((now - before) / before) * 100);
  const up = pct >= 0;
  return (
    <span className="inline-flex items-center gap-1">
      <span className={cx("inline-flex items-center gap-0.5 font-semibold", up ? "text-green-700" : "text-red-600")}>
        <Icon name={up ? "arrowUp" : "arrowDown"} size={12} strokeWidth={2.4} />{Math.abs(pct)}%
      </span>
      <span className="text-slate-500">{period}</span>
    </span>
  );
}

function ListLink({ to, title, meta, right }: { to: string; title: string; meta: ReactNode; right?: ReactNode }) {
  return (
    <li>
      <Link to={to} className="group flex items-center gap-3 rounded-xl px-2 py-2.5 transition hover:bg-slate-50">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-slate-800 group-hover:text-brand-600">{title}</div>
          <div className="truncate text-xs text-slate-500">{meta}</div>
        </div>
        {right}
        <Icon name="arrowRight" size={14} className="shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-brand-500" />
      </Link>
    </li>
  );
}

const Empty = ({ children }: { children: ReactNode }) => (
  <div className="flex min-h-[120px] items-center justify-center rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">{children}</div>
);

const Pill = ({ children, tone }: { children: ReactNode; tone: "critical" | "warning" | "neutral" }) => (
  <span className={cx("inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
    tone === "critical" && "bg-red-50 text-red-700", tone === "warning" && "bg-amber-50 text-amber-800", tone === "neutral" && "bg-slate-100 text-slate-600")}>{children}</span>
);

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

/* ---------- page ---------- */
export default function Dashboard() {
  const { me } = useAuth();
  const tz = -new Date().getTimezoneOffset();
  const { data: d, loading, error, reload } = useFetch(() => api.get<Dash>("/dashboard", { tz_offset_minutes: tz }), [tz]);
  const [trendView, setTrendView] = useState<View>("chart");
  const [outcomeView, setOutcomeView] = useState<View>("chart");
  const [teamView, setTeamView] = useState<View>("chart");
  if (loading && !d) return <Loading />;
  if (error || !d) return <ErrorBox message={error ?? "No data"} onRetry={reload} />;

  const company = d.kind !== "salesman";
  const trend: TrendPoint[] = d.visit_trend ?? [];
  const outcomes: OutcomeRow[] = d.visit_outcomes ?? [];
  const team: SalesmanRow[] = d.salesman_summaries ?? [];
  const upcoming: FollowUp[] = d.upcoming_followups ?? [];
  const recentVisits: any[] = d.recent_visits ?? [];
  const interactions: any[] = d.recent_interactions ?? [];
  const visited: any[] = d.recently_visited_customers ?? [];

  // visit trend: last 7 days vs the 7 days before
  const values = trend.map((p) => p.visits);
  const last7 = sum(values.slice(-7));
  const prev7 = sum(values.slice(-14, -7));
  const day = (iso: string) => new Date(`${iso}T00:00:00`);
  const columns = trend.map((p, i) => ({
    key: p.date, value: p.visits,
    label: i === trend.length - 1 ? "Today" : day(p.date).toLocaleDateString(undefined, { day: "numeric", month: "short" }),
    long: day(p.date).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" }),
  }));

  // follow-up states
  const overdue = d.overdue_followups ?? 0;
  const pending = d.pending_followups ?? 0;
  const completed = d.completed_followups ?? 0;
  const cancelled = d.cancelled_followups ?? 0;
  const segments: Segment[] = [
    { key: "overdue", label: "Overdue", value: overdue, color: STATUS.critical, icon: <Icon name="alert" size={14} /> },
    { key: "upcoming", label: "Upcoming", value: pending - overdue, color: STATUS.warning, icon: <Icon name="clock" size={14} /> },
    { key: "completed", label: "Completed", value: completed, color: STATUS.good, icon: <Icon name="check" size={14} /> },
    { key: "cancelled", label: "Cancelled", value: cancelled, color: STATUS.neutral, icon: <Icon name="x" size={14} /> },
  ];
  const completionRate = completed + pending ? Math.round((completed / (completed + pending)) * 100) : 0;

  // customer coverage (company dashboards)
  const assigned = d.assignment_summary?.assigned_customers ?? 0;
  const unassigned = d.assignment_summary?.unassigned_customers ?? 0;
  const coverage = assigned + unassigned ? Math.round((assigned / (assigned + unassigned)) * 100) : 0;

  const roleName = d.kind === "admin" ? "Administrator" : d.kind === "manager" ? "Manager" : "Salesman";
  const firstName = (me?.full_name ?? "").split(" ")[0];
  const updated = d.generated_at ? new Date(d.generated_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : null;

  return (
    <div className={cx("mx-auto max-w-7xl space-y-6 transition-opacity", loading && "opacity-60")}>
      {/* header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-brand-600">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">{greeting()}, {firstName}</h1>
          <p className="mt-1 text-sm text-slate-500">{roleName} dashboard · {me?.company_name}</p>
        </div>
        <div className="flex items-center gap-3">
          {updated && <span className="text-xs text-slate-500">Updated {updated}</span>}
          <button type="button" onClick={reload} disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-60">
            <Icon name="refresh" size={16} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {company
          ? <Kpi icon="customers" label="Customers" value={d.total_customers ?? 0} sub={`${d.active_customers ?? 0} active`} />
          : <Kpi icon="customers" label="My customers" value={d.assigned_customers ?? 0} sub={`${d.created_by_me_visible ?? 0} created by me`} />}
        <Kpi icon="visits" label="Visits today" value={d.todays_visits ?? 0} sub={<Delta now={last7} before={prev7} period="last 7 days vs prior 7" />}>
          <Sparkline values={values} />
        </Kpi>
        <Kpi icon="followups" label="Pending follow-ups" value={pending} tone="warning" sub={`${completionRate}% completion rate`} />
        <Kpi icon="alert" label="Overdue follow-ups" value={overdue} tone={overdue ? "critical" : "good"} sub={overdue ? "Need attention now" : "All on track"} />
      </div>

      {/* activity + follow-up health */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2" title="Visit activity" subtitle="Visits per day · last 14 days"
          actions={<ViewToggle value={trendView} onChange={setTrendView} />}>
          <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-5xl font-semibold tracking-tight text-slate-900">{compact(last7)}</span>
            <span className="text-sm text-slate-500">visits in the last 7 days · {compact(d.total_visits ?? 0)} all time</span>
          </div>
          {trendView === "table"
            ? <MiniTable head={["Day", "Visits"]} rows={[...columns].reverse().map((c) => [c.long, c.value])} />
            : sum(values) ? <ColumnChart data={columns} /> : <Empty>No visits recorded in the last 14 days.</Empty>}
        </Panel>

        <Panel title="Follow-up health" subtitle="All follow-ups by state">
          <div className="mb-4 flex items-baseline gap-2">
            <span className="text-3xl font-semibold tracking-tight text-slate-900">{compact(pending + completed + cancelled)}</span>
            <span className="text-sm text-slate-500">follow-ups</span>
          </div>
          <StackedBar segments={segments} />
          <Link to="/followups" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700">
            Open follow-ups <Icon name="arrowRight" size={14} />
          </Link>
        </Panel>
      </div>

      {/* team / outcomes / coverage */}
      <div className="grid gap-4 lg:grid-cols-3">
        {company ? (
          <Panel className="lg:col-span-2" title="Team performance" subtitle="Total visits per salesman"
            actions={<ViewToggle value={teamView} onChange={setTeamView} />}>
            {team.length === 0 ? <Empty>No active salesmen yet.</Empty> : teamView === "table" ? (
              <MiniTable head={["Salesman", "Customers", "Visits", "Today", "Pending", "Overdue"]}
                rows={team.map((s) => [s.salesman_name, s.assigned_customers, s.total_visits, s.todays_visits, s.pending_followups, s.overdue_followups])} />
            ) : (
              <HBarChart unit="visits" unitOne="visit" data={[...team].sort((a, b) => b.total_visits - a.total_visits).map((s) => ({
                key: s.salesman_id, label: s.salesman_name, value: s.total_visits,
                note: (
                  <span className="ml-2 inline-flex gap-1 align-middle">
                    <Pill tone="neutral">{s.todays_visits} today</Pill>
                    {s.overdue_followups > 0 && <Pill tone="critical"><Icon name="alert" size={11} />{s.overdue_followups} overdue</Pill>}
                  </span>
                ),
              }))} />
            )}
          </Panel>
        ) : (
          <Panel className="lg:col-span-2" title="Recent customer interactions" subtitle="Latest follow-up outcomes">
            {interactions.length === 0 ? <Empty>No interactions recorded yet.</Empty> : (
              <ul className="-mx-2">
                {interactions.map((o) => (
                  <ListLink key={`${o.follow_up_id}-${o.recorded_at}`} to={`/followups/${o.follow_up_id}`} title={o.outcome_text}
                    meta={<>{o.customer_name} · {fmtDateTime(o.recorded_at)}</>} />
                ))}
              </ul>
            )}
          </Panel>
        )}

        <Panel title="Visit outcomes" subtitle="Last 30 days" actions={<ViewToggle value={outcomeView} onChange={setOutcomeView} />}>
          {outcomes.length === 0 ? <Empty>No visits in the last 30 days.</Empty> : outcomeView === "table"
            ? <MiniTable head={["Outcome", "Visits"]} rows={outcomes.map((o) => [o.outcome, o.visits])} />
            : <HBarChart unit="" data={outcomes.map((o) => ({ key: o.outcome, label: o.outcome, value: o.visits }))} />}
        </Panel>
      </div>

      {/* lists */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Upcoming follow-ups" subtitle="Next scheduled"
          actions={<Link className="text-sm font-medium text-brand-600 hover:text-brand-700" to="/followups?upcoming=true">View all</Link>}>
          {upcoming.length === 0 ? <Empty>No upcoming follow-ups.</Empty> : (
            <ul className="-mx-2">
              {upcoming.slice(0, 6).map((f) => (
                <ListLink key={f.id} to={`/followups/${f.id}`} title={f.title}
                  meta={<>{f.customer?.name ?? "—"}{f.assigned_salesman ? ` · ${f.assigned_salesman.full_name}` : ""}</>}
                  right={<Pill tone="warning"><Icon name="calendar" size={11} />{new Date(f.due_date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</Pill>} />
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Recent visits" subtitle="Latest field activity">
          {recentVisits.length === 0 ? <Empty>No visits recorded yet.</Empty> : (
            <ul className="-mx-2">
              {recentVisits.slice(0, 6).map((v) => (
                <ListLink key={v.id} to={`/visits/${v.id}`} title={v.customer_name}
                  meta={<>{v.user_name} · {fmtDateTime(v.visit_time)}</>}
                  right={v.outcome ? <Pill tone="neutral">{v.outcome}</Pill> : undefined} />
              ))}
            </ul>
          )}
        </Panel>

        {company ? (
          <Panel title="Customer coverage" subtitle="Customers with an assigned salesman">
            <div className="mb-3 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tracking-tight text-slate-900">{coverage}%</span>
              <span className="text-sm text-slate-500">covered</span>
            </div>
            <Meter value={assigned} total={assigned + unassigned} />
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">Assigned</dt><dd className="mt-0.5 text-lg font-semibold">{assigned}</dd></div>
              <div className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">Unassigned</dt><dd className={cx("mt-0.5 text-lg font-semibold", unassigned > 0 && "text-amber-700")}>{unassigned}</dd></div>
            </dl>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-slate-500">{d.total_salesmen ?? 0} active salesmen</span>
              {unassigned > 0 && <Link to="/customers" className="font-medium text-brand-600 hover:text-brand-700">Assign now</Link>}
            </div>
            {visited.length > 0 && (
              <>
                <h3 className="mb-1 mt-5 text-xs font-semibold uppercase tracking-wide text-slate-400">Recently visited</h3>
                <ul className="-mx-2">
                  {visited.slice(0, 3).map((c) => (
                    <ListLink key={c.id} to={`/customers/${c.id}`} title={c.name} meta={<>{c.city || "—"} · {fmtDateTime(c.last_visit)}</>} />
                  ))}
                </ul>
              </>
            )}
          </Panel>
        ) : (
          <Panel title="Today at a glance" subtitle="Your field day">
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">Visits today</dt><dd className="mt-0.5 text-lg font-semibold">{d.todays_visits ?? 0}</dd></div>
              <div className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">Last 7 days</dt><dd className="mt-0.5 text-lg font-semibold">{last7}</dd></div>
              <div className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">Pending</dt><dd className="mt-0.5 text-lg font-semibold">{pending}</dd></div>
              <div className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">Overdue</dt><dd className={cx("mt-0.5 text-lg font-semibold", overdue > 0 && "text-red-600")}>{overdue}</dd></div>
            </dl>
            <Link to="/visits/new" className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-brand-600">
              <Icon name="visits" size={16} /> Record a visit
            </Link>
          </Panel>
        )}
      </div>
    </div>
  );
}
