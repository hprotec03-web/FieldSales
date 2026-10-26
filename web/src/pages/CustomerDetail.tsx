import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, Card, DataTable, ErrorBox, Field, Input, Loading, Modal, PageHeader, Select, Textarea, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { errorMessage, fmtDateTime, localInputToIso, toLocalInput } from "../lib/format";
import type { ActivityItem, Assignment, Customer, FollowUp, Page, User, Visit } from "../lib/types";

function PrivatePhoto({ path }: { path: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    api.imageUrl(path).then((u) => { url = u; setSrc(u); }).catch(() => setFailed(true));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (failed) return <p className="text-sm text-slate-500">Photo unavailable.</p>;
  return src ? <img src={src} alt="Business" className="max-h-56 rounded-md border" /> : <Loading />;
}

export default function CustomerDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { can, me } = useAuth();
  const c = useFetch(() => api.get<Customer>(`/customers/${id}`), [id]);
  const assignments = useFetch(() => api.get<Assignment[]>(`/customers/${id}/assignments`), [id]);
  const activity = useFetch(() => (can("Customer.View") ? api.get<ActivityItem[]>(`/customers/${id}/activity`) : Promise.resolve([])), [id]);
  const visits = useFetch(() => api.get<Page<Visit>>("/visits", { customer_id: id, page_size: 10 }), [id]);
  const followups = useFetch(() => api.get<FollowUp[]>(`/customers/${id}/followups`), [id]);
  const [assignOpen, setAssignOpen] = useState(false);
  const [fuOpen, setFuOpen] = useState(false);
  const [salesmanId, setSalesmanId] = useState("");
  const [busy, setBusy] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [fu, setFu] = useState({ title: "", notes: "", due: toLocalInput(new Date(Date.now() + 86400000)) });
  const salesmen = useFetch(() => (can("Customer.Assign") ? api.get<Page<User>>("/users", { scope: "assigned", status: "Active", page_size: 200 }) : Promise.resolve(null)), []);

  const reloadAll = () => { c.reload(); assignments.reload(); activity.reload(); };
  const run = async (fn: () => Promise<unknown>, ok: string, done?: () => void) => {
    setBusy(true); setModalError(null);
    try { await fn(); toast(ok); done?.(); reloadAll(); } catch (e) { setModalError(errorMessage(e)); toast(errorMessage(e), "error"); } finally { setBusy(false); }
  };

  if (c.loading && !c.data) return <Loading />;
  if (c.error || !c.data) return <ErrorBox message={c.error ?? "Customer not found"} onRetry={c.reload} />;
  const cust = c.data;
  const canVisit = can("Visit.Create");

  return (
    <>
      <PageHeader title={cust.name} subtitle={`${cust.city}, ${cust.country}`}
        actions={<>
          {canVisit && <Link to={`/visits/new?customer_id=${cust.id}`}><Button>Record visit</Button></Link>}
          {can("FollowUp.Create") && <Button variant="secondary" onClick={() => { setModalError(null); setFuOpen(true); }}>New follow-up</Button>}
          {can("Customer.Assign") && <Button variant="secondary" onClick={() => { setModalError(null); setAssignOpen(true); }}>{cust.assigned_salesman ? "Reassign" : "Assign"}</Button>}
          {can("Customer.Edit") && <Link to={`/customers/${cust.id}/edit`}><Button variant="secondary">Edit</Button></Link>}
          {can("Customer.Edit") && (
            <Button variant="secondary" loading={busy} onClick={() => run(() => api.patch(`/customers/${cust.id}/status`, { status: cust.status === "Active" ? "Inactive" : "Active" }), "Status updated")}>
              {cust.status === "Active" ? "Deactivate" : "Activate"}
            </Button>
          )}
        </>} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Details" className="lg:col-span-2">
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            {([["Status", <Badge key="s">{cust.status}</Badge>], ["Mobile", cust.mobile], ["Business type", cust.business_type], ["Product", cust.product],
              ["Contact person", cust.contact_person], ["Contact mobile", cust.contact_person_mobile], ["Email", cust.email], ["Address", cust.address],
              ["Location", cust.location_url ? <a key="l" className="text-brand-600 hover:underline" href={cust.location_url} target="_blank" rel="noopener noreferrer">Open map</a> : null],
              ["Responsible salesman", cust.assigned_salesman?.full_name ?? "Unassigned"], ["Created", fmtDateTime(cust.created_at)], ["Notes", cust.notes]] as [string, any][])
              .map(([k, v]) => <div key={k}><dt className="text-xs uppercase text-slate-500">{k}</dt><dd>{v || "—"}</dd></div>)}
          </dl>
        </Card>
        <Card title="Business photo">
          {cust.business_photo_url ? <PrivatePhoto path={cust.business_photo_url} /> : <p className="text-sm text-slate-500">No photo uploaded.</p>}
          {(can("Customer.Edit") || (me?.role.data_scope === "assigned" && canVisit)) && (
            <label className="mt-3 block text-sm">
              <span className="sr-only">Upload photo</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) run(() => api.upload(`/customers/${cust.id}/photo`, f), "Photo uploaded"); e.target.value = ""; }} />
            </label>
          )}
        </Card>

        <Card title="Visits" className="lg:col-span-2" actions={<Link className="text-sm text-brand-600" to={`/visits?customer_id=${cust.id}`}>All visits</Link>}>
          <DataTable<Visit> rows={visits.data?.items} loading={visits.loading} error={visits.error} onRetry={visits.reload} rowKey={(v) => v.id} onRowClick={(v) => nav(`/visits/${v.id}`)}
            empty="No visits recorded for this customer." columns={[
              { header: "When", cell: (v) => fmtDateTime(v.visit_time) }, { header: "By", cell: (v) => v.user_name }, { header: "Purpose", cell: (v) => v.purpose ?? "—" }, { header: "Outcome", cell: (v) => v.outcome ?? "—" }]} />
        </Card>
        <Card title="Assignment history">
          <DataTable<Assignment> rows={assignments.data ?? undefined} loading={assignments.loading} error={assignments.error} onRetry={assignments.reload} rowKey={(a) => a.id} empty="Never assigned."
            columns={[{ header: "Salesman", cell: (a) => <>{a.salesman_name} {a.is_active && <Badge>Active</Badge>}</> }, { header: "From", cell: (a) => fmtDateTime(a.assigned_at) }, { header: "To", cell: (a) => (a.ended_at ? fmtDateTime(a.ended_at) : "—") }]} />
        </Card>

        <Card title="Follow-ups" className="lg:col-span-2">
          <DataTable<FollowUp> rows={followups.data ?? undefined} loading={followups.loading} error={followups.error} onRetry={followups.reload} rowKey={(f) => f.id} onRowClick={(f) => nav(`/followups/${f.id}`)}
            empty="No follow-ups." columns={[
              { header: "Title", cell: (f) => f.title }, { header: "Due", cell: (f) => fmtDateTime(f.due_date) },
              { header: "Status", cell: (f) => <Badge>{f.is_overdue ? "Overdue" : f.status}</Badge> }]} />
        </Card>
        <Card title="Activity">
          {activity.loading ? <Loading /> : activity.error ? <ErrorBox message={activity.error} onRetry={activity.reload} /> : !activity.data?.length ? <p className="text-sm text-slate-500">No activity yet.</p> : (
            <ol className="space-y-3 text-sm">
              {activity.data.slice(0, 15).map((a, i) => (
                <li key={i} className="border-l-2 border-brand-100 pl-3"><div className="text-xs text-slate-500">{fmtDateTime(a.at)} · {a.user_name}</div><div>{a.summary}</div></li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <Modal open={assignOpen} title={cust.assigned_salesman ? "Reassign customer" : "Assign customer"} onClose={() => setAssignOpen(false)}>
        {modalError && <ErrorBox message={modalError} />}
        <p className="mb-3 text-sm text-slate-600">The previous salesman will immediately lose access to this customer and its follow-ups. History is preserved.</p>
        <Field label="Salesman"><Select value={salesmanId} onChange={(e) => setSalesmanId(e.target.value)}><option value="">Select…</option>
          {salesmen.data?.items.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}</Select></Field>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setAssignOpen(false)}>Cancel</Button>
          <Button disabled={!salesmanId} loading={busy} onClick={() => run(() => api.post(`/customers/${cust.id}/assignments`, { salesman_id: Number(salesmanId) }), "Customer assigned", () => setAssignOpen(false))}>Confirm</Button>
        </div>
      </Modal>

      <Modal open={fuOpen} title="New follow-up" onClose={() => setFuOpen(false)}>
        {modalError && <ErrorBox message={modalError} />}
        <div className="space-y-3">
          <Field label="Title" hint={`Default: Follow-up with ${cust.name}`}><Input value={fu.title} onChange={(e) => setFu({ ...fu, title: e.target.value })} /></Field>
          <Field label="Due" required><Input type="datetime-local" value={fu.due} onChange={(e) => setFu({ ...fu, due: e.target.value })} /></Field>
          <Field label="Notes"><Textarea value={fu.notes} onChange={(e) => setFu({ ...fu, notes: e.target.value })} /></Field>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setFuOpen(false)}>Cancel</Button>
          <Button disabled={!fu.due} loading={busy} onClick={() => run(async () => { const r = await api.post<FollowUp>("/followups", { customer_id: cust.id, title: fu.title || null, notes: fu.notes || null, due_date: localInputToIso(fu.due) }); followups.reload(); nav(`/followups/${r.id}`); }, "Follow-up created", () => setFuOpen(false))}>Create</Button>
        </div>
      </Modal>
    </>
  );
}
