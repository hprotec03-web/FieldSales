import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, DataTable, ErrorBox, Field, Input, Modal, PageHeader, Pagination, Select, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { ApiError, api } from "../lib/api";
import { errorMessage } from "../lib/format";
import type { Branch, Page, RoleFull, User } from "../lib/types";

type Draft = { id?: number; username: string; full_name: string; password: string; role_id: string; branch_id: string; email: string; mobile: string; status: string };
const empty: Draft = { username: "", full_name: "", password: "", role_id: "", branch_id: "", email: "", mobile: "", status: "Active" };

export default function Users() {
  const { can, me } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState(""); const [status, setStatus] = useState(""); const [page, setPage] = useState(1);
  const users = useFetch(() => api.get<Page<User>>("/users", { q, status, page, page_size: 25 }), [q, status, page]);
  const roles = useFetch(() => api.get<RoleFull[]>("/roles"), []);
  const branches = useFetch(() => (can("Branch.View") ? api.get<Branch[]>("/branches") : Promise.resolve([])), []);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [fieldErr, setFieldErr] = useState<Record<string, string>>({});

  const save = async () => {
    if (!draft) return;
    setBusy(true); setErr(null); setFieldErr({});
    const body: Record<string, unknown> = { full_name: draft.full_name, role_id: Number(draft.role_id), branch_id: draft.branch_id ? Number(draft.branch_id) : null, email: draft.email || null, mobile: draft.mobile || null };
    try {
      if (draft.id) { body.status = draft.status; if (draft.password) body.password = draft.password; await api.put(`/users/${draft.id}`, body); }
      else await api.post("/users", { ...body, username: draft.username, password: draft.password });
      toast("User saved"); setDraft(null); users.reload();
    } catch (e) { if (e instanceof ApiError && Object.keys(e.fieldErrors).length) setFieldErr(e.fieldErrors); else setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  const deactivate = async (u: User) => {
    if (!confirm(`Deactivate ${u.full_name}? They will no longer be able to sign in.`)) return;
    try { await api.del(`/users/${u.id}`); toast("User deactivated"); users.reload(); } catch (e) { toast(errorMessage(e), "error"); }
  };
  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft({ ...draft!, [k]: e.target.value });

  return (
    <>
      <PageHeader title="Users" actions={can("User.Create") && <Button onClick={() => { setErr(null); setFieldErr({}); setDraft({ ...empty, role_id: String(roles.data?.find((r) => r.name === "Salesman")?.id ?? "") }); }}>New user</Button>} />
      <div className="mb-3 grid gap-2 sm:grid-cols-3">
        <Input placeholder="Search name or username…" aria-label="Search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option><option>Active</option><option>Inactive</option><option>Suspended</option></Select>
      </div>
      <DataTable<User> rows={users.data?.items} loading={users.loading} error={users.error} onRetry={users.reload} rowKey={(u) => u.id} empty="No users found."
        columns={[
          { header: "Name", cell: (u) => <span className="font-medium">{u.full_name}</span> }, { header: "Username", cell: (u) => u.username }, { header: "Role", cell: (u) => u.role.name },
          { header: "Status", cell: (u) => <Badge>{u.status}</Badge> },
          { header: "", cell: (u) => (<div className="flex gap-2">
            {can("User.Edit") && <Button variant="secondary" onClick={() => { setErr(null); setFieldErr({}); setDraft({ id: u.id, username: u.username, full_name: u.full_name, password: "", role_id: String(u.role_id), branch_id: u.branch_id ? String(u.branch_id) : "", email: u.email ?? "", mobile: u.mobile ?? "", status: u.status }); }}>Edit</Button>}
            {can("User.Delete") && u.id !== me?.id && u.status !== "Inactive" && <Button variant="danger" onClick={() => deactivate(u)}>Deactivate</Button>}
          </div>) }]} />
      {users.data && <Pagination page={page} pageSize={users.data.page_size} total={users.data.total} onChange={setPage} />}

      <Modal open={!!draft} title={draft?.id ? "Edit user" : "New user"} onClose={() => setDraft(null)}>
        {draft && (<div className="space-y-3">
          {err && <ErrorBox message={err} />}
          {!draft.id && <Field label="Username" required error={fieldErr.username}><Input value={draft.username} onChange={set("username")} autoComplete="off" /></Field>}
          <Field label="Full name" required error={fieldErr.full_name}><Input value={draft.full_name} onChange={set("full_name")} /></Field>
          <Field label={draft.id ? "New password (leave blank to keep)" : "Password"} required={!draft.id} error={fieldErr.password} hint="At least 8 characters, with letters and digits."><Input type="password" value={draft.password} onChange={set("password")} autoComplete="new-password" /></Field>
          <Field label="Role" required error={fieldErr.role_id}><Select value={draft.role_id} onChange={set("role_id")}><option value="">Select…</option>{roles.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select></Field>
          {!!branches.data?.length && <Field label="Branch"><Select value={draft.branch_id} onChange={set("branch_id")}><option value="">None</option>{branches.data.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</Select></Field>}
          <Field label="Email" error={fieldErr.email}><Input type="email" value={draft.email} onChange={set("email")} /></Field>
          <Field label="Mobile" error={fieldErr.mobile}><Input value={draft.mobile} onChange={set("mobile")} /></Field>
          {draft.id && <Field label="Status"><Select value={draft.status} onChange={set("status")} disabled={draft.id === me?.id}><option>Active</option><option>Inactive</option><option>Suspended</option></Select></Field>}
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
            <Button loading={busy} disabled={!draft.full_name || !draft.role_id || (!draft.id && (!draft.username || !draft.password))} onClick={save}>Save</Button></div>
        </div>)}
      </Modal>
    </>
  );
}
