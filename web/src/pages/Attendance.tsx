import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Icon, IconName } from "../components/icons";
import { ErrorBox, Loading } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";

/* ---------- API types ---------- */
interface Place { latitude: number | null; longitude: number | null; accuracy: number | null; address: string | null; area: string | null; is_mocked: boolean }
interface Break { id: number; break_type: string; note: string | null; start_at: string; start: Place; end_at: string | null; end: Place | null; minutes: number }
interface Session {
  id: number; user_id: number; user_name: string; branch_name: string | null; work_date: string; status: string;
  state: "working" | "on_break" | "checked_out"; check_in_at: string; check_in: Place; check_in_note: string | null;
  check_out_at: string | null; check_out: Place | null; check_out_method: string | null; device_info: string | null;
  breaks: Break[]; break_minutes: number; worked_minutes: number; any_mocked: boolean;
}
interface TeamRow { user_id: number; user_name: string; branch_name: string | null; session: Session | null }
interface TeamDay { date: string; rows: TeamRow[]; generated_at: string }
interface TimelineEvent { key: string; kind: "in" | "break" | "back" | "out"; title: string; at: string; place: Place }

/* ---------- helpers ---------- */
const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
const time = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "—");
const hm = (min: number) => `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}m`;
const placeLabel = (p?: Place | null) =>
  !p || p.latitude == null ? "—" : p.area || p.address || `${p.latitude.toFixed(5)}, ${p.longitude!.toFixed(5)}`;
const mapsUrl = (p: Place) => `https://www.google.com/maps?q=${p.latitude},${p.longitude}`;
const embedUrl = (p: Place) => {
  const lat = p.latitude!, lng = p.longitude!, dx = 0.012, dy = 0.007;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${lng - dx},${lat - dy},${lng + dx},${lat + dy}&layer=mapnik&marker=${lat},${lng}`;
};
const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Worked minutes "now": the server value plus time elapsed since it was computed (only while working). */
function liveWorked(s: Session, generatedAt: string, now: number) {
  if (s.state !== "working") return s.worked_minutes;
  return s.worked_minutes + Math.max(0, Math.floor((now - new Date(generatedAt).getTime()) / 60000));
}

function timeline(s: Session): TimelineEvent[] {
  const ev: TimelineEvent[] = [{ key: "in", kind: "in", title: "Checked in", at: s.check_in_at, place: s.check_in }];
  for (const b of s.breaks) {
    ev.push({ key: `b${b.id}`, kind: "break", title: `${b.break_type} break started`, at: b.start_at, place: b.start });
    if (b.end_at && b.end) ev.push({ key: `e${b.id}`, kind: "back", title: `Back to work · ${b.minutes}m break`, at: b.end_at, place: b.end });
  }
  if (s.check_out_at) {
    const how = s.check_out_method === "logout" ? " (at logout)" : s.check_out_method === "auto" ? " (automatic)" : "";
    ev.push({ key: "out", kind: "out", title: `Checked out${how}`, at: s.check_out_at, place: s.check_out ?? s.check_in });
  }
  return ev;
}

const STATE: Record<string, { label: string; dot: string; pill: string }> = {
  working: { label: "Working", dot: "bg-green-500", pill: "bg-green-50 text-green-700" },
  on_break: { label: "On break", dot: "bg-amber-400", pill: "bg-amber-50 text-amber-800" },
  checked_out: { label: "Checked out", dot: "bg-slate-400", pill: "bg-slate-100 text-slate-600" },
  absent: { label: "Not checked in", dot: "bg-red-400", pill: "bg-red-50 text-red-700" },
};
const EVENT_STYLE: Record<TimelineEvent["kind"], { icon: IconName; cls: string }> = {
  in: { icon: "arrowRight", cls: "bg-green-50 text-green-700" },
  break: { icon: "clock", cls: "bg-amber-50 text-amber-700" },
  back: { icon: "refresh", cls: "bg-brand-50 text-brand-600" },
  out: { icon: "logout", cls: "bg-red-50 text-red-600" },
};

function Panel({ title, subtitle, actions, children, className }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("min-w-0 rounded-2xl border border-slate-200/70 bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]", className)}>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>{subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}</div>
        {actions}
      </header>
      {children}
    </section>
  );
}

function Kpi({ label, value, dot, sub }: { label: string; value: ReactNode; dot?: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-slate-200/70 bg-white p-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-600">{dot && <span className={cx("h-2.5 w-2.5 rounded-full", dot)} />}{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

/* ---------- page ---------- */
export default function Attendance() {
  const [date, setDate] = useState(localToday());
  const tz = -new Date().getTimezoneOffset();
  const { data, loading, error, reload } = useFetch(() => api.get<TeamDay>("/attendance/team", { date, tz_offset_minutes: tz }), [date, tz]);
  const [selected, setSelected] = useState<number | null>(null);
  const [eventKey, setEventKey] = useState<string | null>(null);
  const [view, setView] = useState<"team" | "areas">("team");
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t); }, []);

  const rows = data?.rows ?? [];
  const isToday = date === localToday();
  const stateOf = (r: TeamRow) => r.session?.state ?? "absent";
  const counts = useMemo(() => {
    const c = { working: 0, on_break: 0, checked_out: 0, absent: 0 } as Record<string, number>;
    rows.forEach((r) => { c[stateOf(r)] += 1; });
    return c;
  }, [rows]);
  const present = rows.filter((r) => r.session);
  const avgWorked = present.length && data ? Math.round(present.reduce((a, r) => a + liveWorked(r.session!, data.generated_at, now), 0) / present.length) : 0;

  // keep a sensible selection: the chosen salesman if present, else the first one with a session
  const current = rows.find((r) => r.user_id === selected && r.session) ?? present[0];
  const events = current?.session ? timeline(current.session) : [];
  const shown = events.find((e) => e.key === eventKey) ?? events[events.length - 1];

  // location-wise: every event of the day grouped by area
  const areas = useMemo(() => {
    const m = new Map<string, { area: string; people: Set<string>; events: number; checkIns: number; breaks: number; checkOuts: number; place: Place }>();
    for (const r of present) {
      for (const e of timeline(r.session!)) {
        if (e.place.latitude == null) continue;
        const area = e.place.area || `~${e.place.latitude.toFixed(2)}, ${e.place.longitude!.toFixed(2)}`;
        const g = m.get(area) ?? { area, people: new Set<string>(), events: 0, checkIns: 0, breaks: 0, checkOuts: 0, place: e.place };
        g.people.add(r.user_name); g.events += 1;
        if (e.kind === "in") g.checkIns += 1; else if (e.kind === "break") g.breaks += 1; else if (e.kind === "out") g.checkOuts += 1;
        m.set(area, g);
      }
    }
    return [...m.values()].sort((a, b) => b.events - a.events);
  }, [present]);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox message={error} onRetry={reload} />;

  return (
    <div className={cx("mx-auto max-w-7xl space-y-6 transition-opacity", loading && "opacity-60")}>
      {/* header + filters */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-brand-600">Field team</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">Attendance</h1>
          <p className="mt-1 text-sm text-slate-500">Check-in, breaks and check-out with GPS location for every salesman.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={date} max={localToday()} onChange={(e) => e.target.value && setDate(e.target.value)}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none" aria-label="Day" />
          {!isToday && <button type="button" onClick={() => setDate(localToday())} className="rounded-xl px-3 py-2 text-sm font-medium text-brand-600 hover:bg-brand-50">Today</button>}
          <button type="button" onClick={reload} disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-60">
            <Icon name="refresh" size={16} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
          <Link to="/reports" className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-3.5 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-600">
            <Icon name="reports" size={16} /> Reports
          </Link>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Kpi label="Working" value={counts.working} dot="bg-green-500" />
        <Kpi label="On break" value={counts.on_break} dot="bg-amber-400" />
        <Kpi label="Checked out" value={counts.checked_out} dot="bg-slate-400" />
        <Kpi label="Not checked in" value={counts.absent} dot="bg-red-400" sub={`of ${rows.length} salesmen`} />
        <Kpi label="Average worked" value={hm(avgWorked)} sub={present.length ? `${present.length} present` : "nobody present"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        {/* team list / areas */}
        <Panel className="lg:col-span-3" title={view === "team" ? "Team" : "Location-wise"}
          subtitle={view === "team" ? new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" }) : "All attendance events of the day grouped by area"}
          actions={
            <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium" role="group" aria-label="View">
              {(["team", "areas"] as const).map((v) => (
                <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}
                  className={cx("rounded-md px-2.5 py-1 transition", view === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700")}>
                  {v === "team" ? "By salesman" : "By area"}
                </button>
              ))}
            </div>
          }>
          {view === "team" ? (
            rows.length === 0 ? <Empty>No salesmen found.</Empty> : (
              <div className="-mx-5 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-y border-slate-100 bg-slate-50/60 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                      <th className="px-5 py-2.5">Salesman</th><th className="px-3 py-2.5">Status</th><th className="px-3 py-2.5">Check-in</th>
                      <th className="px-3 py-2.5">Check-out</th><th className="px-3 py-2.5 text-right">Breaks</th><th className="px-5 py-2.5 text-right">Worked</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {rows.map((r) => {
                      const s = r.session, st = STATE[stateOf(r)], active = current?.user_id === r.user_id && !!s;
                      return (
                        <tr key={r.user_id} onClick={() => { if (s) { setSelected(r.user_id); setEventKey(null); } }}
                          className={cx(s && "cursor-pointer", active ? "bg-brand-50/60" : s && "hover:bg-slate-50")}>
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-3">
                              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
                                {r.user_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
                              </span>
                              <div className="min-w-0">
                                <div className="truncate font-medium text-slate-800">{r.user_name}</div>
                                <div className="truncate text-xs text-slate-500">{r.branch_name ?? "—"}</div>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <span className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", st.pill)}>
                              <span className={cx("h-1.5 w-1.5 rounded-full", st.dot)} />{st.label}
                            </span>
                            {s?.any_mocked && <span className="ml-1 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700">Fake GPS</span>}
                          </td>
                          <td className="px-3 py-3">
                            <div className="font-medium text-slate-800">{time(s?.check_in_at)}</div>
                            <div className="max-w-[180px] truncate text-xs text-slate-500" title={placeLabel(s?.check_in)}>{s ? placeLabel(s.check_in) : ""}</div>
                          </td>
                          <td className="px-3 py-3">
                            <div className="font-medium text-slate-800">{s?.check_out_at ? time(s.check_out_at) : s ? "—" : ""}</div>
                            <div className="max-w-[180px] truncate text-xs text-slate-500">{s?.check_out ? placeLabel(s.check_out) : ""}</div>
                          </td>
                          <td className="px-3 py-3 text-right" style={{ fontVariantNumeric: "tabular-nums" }}>
                            {s ? <><div className="font-medium text-slate-800">{s.breaks.length}</div><div className="text-xs text-slate-500">{hm(s.break_minutes)}</div></> : ""}
                          </td>
                          <td className="px-5 py-3 text-right font-semibold text-slate-900" style={{ fontVariantNumeric: "tabular-nums" }}>
                            {s && data ? hm(liveWorked(s, data.generated_at, now)) : ""}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          ) : areas.length === 0 ? <Empty>No locations recorded for this day.</Empty> : (
            <ul className="space-y-2">
              {areas.map((a) => (
                <li key={a.area} className="flex items-center gap-3 rounded-xl border border-slate-100 p-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><Icon name="visits" /></span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-slate-800">{a.area}</div>
                    <div className="truncate text-xs text-slate-500">{[...a.people].join(", ")}</div>
                  </div>
                  <div className="hidden gap-1 sm:flex">
                    {a.checkIns > 0 && <span className="rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-700">{a.checkIns} in</span>}
                    {a.breaks > 0 && <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800">{a.breaks} break</span>}
                    {a.checkOuts > 0 && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">{a.checkOuts} out</span>}
                  </div>
                  <a href={mapsUrl(a.place)} target="_blank" rel="noreferrer" className="shrink-0 text-sm font-medium text-brand-600 hover:underline">Map</a>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* selected salesman's day */}
        <Panel className="lg:col-span-2" title={current ? current.user_name : "Day timeline"}
          subtitle={current?.session ? `${hm(liveWorked(current.session, data!.generated_at, now))} worked · ${hm(current.session.break_minutes)} breaks` : "Select a salesman to see their day"}>
          {!current?.session ? <Empty>{rows.length ? "Nobody has checked in on this day." : "No salesmen found."}</Empty> : (
            <>
              {shown && shown.place.latitude != null && (
                <div className="mb-4 overflow-hidden rounded-xl border border-slate-200">
                  <iframe key={shown.key + current.user_id} title={`Map: ${shown.title}`} src={embedUrl(shown.place)} className="h-56 w-full" loading="lazy" />
                  <div className="flex items-center justify-between gap-2 bg-slate-50 px-3 py-2 text-xs">
                    <span className="truncate text-slate-600">{shown.title} · {time(shown.at)}</span>
                    <a href={mapsUrl(shown.place)} target="_blank" rel="noreferrer" className="shrink-0 font-medium text-brand-600 hover:underline">Open in Google Maps</a>
                  </div>
                </div>
              )}
              <ol className="relative space-y-1 before:absolute before:bottom-3 before:left-[17px] before:top-3 before:w-px before:bg-slate-200">
                {events.map((e) => {
                  const st = EVENT_STYLE[e.kind];
                  return (
                    <li key={e.key}>
                      <button type="button" onClick={() => setEventKey(e.key)}
                        className={cx("relative flex w-full items-start gap-3 rounded-xl p-1.5 text-left transition", shown?.key === e.key ? "bg-slate-50" : "hover:bg-slate-50")}>
                        <span className={cx("relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-4 ring-white", st.cls)}><Icon name={st.icon} size={14} /></span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-baseline justify-between gap-2">
                            <span className="truncate text-sm font-medium text-slate-800">{e.title}</span>
                            <span className="shrink-0 text-xs font-semibold text-slate-700">{time(e.at)}</span>
                          </span>
                          <span className="block truncate text-xs text-slate-500">
                            {placeLabel(e.place)}{e.place.accuracy != null && ` · ±${Math.round(e.place.accuracy)} m`}
                            {e.place.is_mocked && <span className="ml-1 font-semibold text-red-600">· Fake GPS</span>}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
              {(current.session.check_in_note || current.session.device_info) && (
                <dl className="mt-4 space-y-1 border-t border-slate-100 pt-3 text-xs">
                  {current.session.check_in_note && <div className="flex gap-2"><dt className="w-16 shrink-0 text-slate-500">Note</dt><dd className="text-slate-700">{current.session.check_in_note}</dd></div>}
                  {current.session.device_info && <div className="flex gap-2"><dt className="w-16 shrink-0 text-slate-500">Device</dt><dd className="truncate text-slate-700">{current.session.device_info}</dd></div>}
                </dl>
              )}
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}

const Empty = ({ children }: { children: ReactNode }) => (
  <div className="flex min-h-[140px] items-center justify-center rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">{children}</div>
);
