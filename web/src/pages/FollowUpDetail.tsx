import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, Card, ErrorBox, Field, Input, Loading, PageHeader, Textarea, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { errorMessage, fmtDateTime, localInputToIso, toLocalInput } from "../lib/format";
import type { FollowUpDetail } from "../lib/types";

export default function FollowUpDetailPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const toast = useToast();
  const { data: f, loading, error, reload } = useFetch(() => api.get<FollowUpDetail>(`/followups/${id}`), [id]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [edit, setEdit] = useState<{ title: string; due: string; notes: string } | null>(null);

  const run = async (fn: () => Promise<unknown>, ok: string, after?: () => void) => {
    setBusy(true); setFormError(null);
    try { await fn(); toast(ok); after?.(); reload(); } catch (e) { setFormError(errorMessage(e)); } finally { setBusy(false); }
  };

  if (loading && !f) return <Loading />;
  if (error || !f) return <ErrorBox message={error ?? "Follow-up not found"} onRetry={reload} />;
  const pending = f.status === "Pending";

  return (
    <>
      <PageHeader title={f.title} subtitle={`Customer: ${f.customer?.name ?? "—"}`}
        actions={<>
          {pending && can("FollowUp.Complete") && <Button loading={busy} onClick={() => run(() => api.post(`/followups/${f.id}/complete`, { outcome_text: text.trim() || null }), "Follow-up completed", () => setText(""))}>Mark completed</Button>}
          {pending && can("FollowUp.Edit") && <Button variant="secondary" loading={busy} onClick={() => run(() => api.post(`/followups/${f.id}/status`, { status: "Cancelled" }), "Follow-up cancelled")}>Cancel follow-up</Button>}
          {f.status === "Cancelled" && can("FollowUp.Edit") && <Button variant="secondary" loading={busy} onClick={() => run(() => api.post(`/followups/${f.id}/status`, { status: "Pending" }), "Follow-up reopened")}>Reopen</Button>}
        </>} />
      {formError && <div className="mb-3"><ErrorBox message={formError} /></div>}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Follow-up details" className="lg:col-span-2" actions={pending && can("FollowUp.Edit") && !edit ? <Button variant="secondary" onClick={() => setEdit({ title: f.title, due: toLocalInput(new Date(f.due_date)), notes: f.notes ?? "" })}>Edit</Button> : undefined}>
          {edit ? (
            <div className="space-y-3">
              <Field label="Title" required><Input value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} /></Field>
              <Field label="Due date" required><Input type="datetime-local" value={edit.due} onChange={(e) => setEdit({ ...edit, due: e.target.value })} /></Field>
              <Field label="Notes"><Textarea value={edit.notes} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} /></Field>
              <div className="flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setEdit(null)}>Cancel</Button>
                <Button loading={busy} disabled={!edit.title.trim() || !edit.due} onClick={() => run(() => api.put(`/followups/${f.id}`, { title: edit.title.trim(), due_date: localInputToIso(edit.due), notes: edit.notes || null }), "Follow-up updated", () => setEdit(null))}>Save</Button>
              </div>
            </div>
          ) : (
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-xs uppercase text-slate-500">Status</dt><dd><Badge>{f.is_overdue ? "Overdue" : f.status}</Badge></dd></div>
              <div><dt className="text-xs uppercase text-slate-500">Due</dt><dd>{fmtDateTime(f.due_date)}</dd></div>
              <div><dt className="text-xs uppercase text-slate-500">Responsible salesman</dt><dd>{f.assigned_salesman?.full_name ?? "Unassigned"}</dd></div>
              <div><dt className="text-xs uppercase text-slate-500">Created by</dt><dd>{f.created_by_name} · {fmtDateTime(f.created_at)}</dd></div>
              {f.completed_at && <div><dt className="text-xs uppercase text-slate-500">Completed</dt><dd>{fmtDateTime(f.completed_at)}</dd></div>}
              <div className="sm:col-span-2"><dt className="text-xs uppercase text-slate-500">Notes</dt><dd>{f.notes || "—"}</dd></div>
            </dl>
          )}
        </Card>
        <Card title="Customer">
          {f.customer && (<div className="space-y-1 text-sm">
            <Link className="font-medium text-brand-600 hover:underline" to={`/customers/${f.customer.id}`}>{f.customer.name}</Link>
            <div>{f.customer.mobile}</div><div>{f.customer.city}</div><Badge>{f.customer.status}</Badge>
          </div>)}
        </Card>

        <Card title={`Outcome history (${f.outcomes.length})`} className="lg:col-span-2">
          {f.outcomes.length === 0 ? <p className="text-sm text-slate-500">No outcomes recorded yet.</p> : (
            <ol className="space-y-3">
              {f.outcomes.map((o) => (
                <li key={o.id} className="rounded-md border border-slate-100 bg-slate-50 p-3 text-sm">
                  <div className="mb-1 text-xs text-slate-500">{fmtDateTime(o.recorded_at)} · {o.recorded_by_name}</div>
                  <div className="whitespace-pre-wrap">{o.outcome_text}</div>
                </li>
              ))}
            </ol>
          )}
          <p className="mt-3 text-xs text-slate-500">History is append-only: entries cannot be edited or deleted.</p>
        </Card>
        {pending && can("FollowUp.Edit") && (
          <Card title="Add outcome">
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) run(() => api.post(`/followups/${f.id}/outcomes`, { outcome_text: text.trim() }), "Outcome added", () => setText("")); }}>
              <Field label="What happened?" required><Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Customer requested a demonstration" /></Field>
              <Button type="submit" loading={busy} disabled={!text.trim()} className="w-full">Add outcome</Button>
            </form>
          </Card>
        )}
      </div>
    </>
  );
}
