import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, DataTable, ErrorBox, Field, Input, Modal, PageHeader, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { errorMessage } from "../lib/format";
import type { Branch } from "../lib/types";

export default function Branches() {
  const { can } = useAuth();
  const toast = useToast();
  const list = useFetch(() => api.get<Branch[]>("/branches"), []);
  const [d, setD] = useState<{ id?: number; name: string; city: string; address: string; is_active: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    if (!d) return; setBusy(true); setErr(null);
    const body = { name: d.name, city: d.city || null, address: d.address || null, is_active: d.is_active };
    try { d.id ? await api.put(`/branches/${d.id}`, body) : await api.post("/branches", body); toast("Branch saved"); setD(null); list.reload(); } catch (e) { setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  const remove = async (b: Branch) => {
    if (!confirm(`Delete branch “${b.name}”?`)) return;
    try { await api.del(`/branches/${b.id}`); toast("Branch deleted"); list.reload(); } catch (e) { toast(errorMessage(e), "error"); }
  };

  return (
    <>
      <PageHeader title="Branches" actions={can("Branch.Create") && <Button onClick={() => { setErr(null); setD({ name: "", city: "", address: "", is_active: true }); }}>New branch</Button>} />
      <DataTable<Branch> rows={list.data ?? undefined} loading={list.loading} error={list.error} onRetry={list.reload} rowKey={(b) => b.id} empty="No branches yet."
        columns={[{ header: "Name", cell: (b) => b.name }, { header: "City", cell: (b) => b.city ?? "—" }, { header: "Status", cell: (b) => <Badge>{b.is_active ? "Active" : "Inactive"}</Badge> },
          { header: "", cell: (b) => (<div className="flex gap-2">
            {can("Branch.Edit") && <Button variant="secondary" onClick={() => { setErr(null); setD({ id: b.id, name: b.name, city: b.city ?? "", address: b.address ?? "", is_active: b.is_active }); }}>Edit</Button>}
            {can("Branch.Delete") && <Button variant="danger" onClick={() => remove(b)}>Delete</Button>}</div>) }]} />
      <Modal open={!!d} title={d?.id ? "Edit branch" : "New branch"} onClose={() => setD(null)}>
        {d && (<div className="space-y-3">{err && <ErrorBox message={err} />}
          <Field label="Name" required><Input value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} /></Field>
          <Field label="City"><Input value={d.city} onChange={(e) => setD({ ...d, city: e.target.value })} /></Field>
          <Field label="Address"><Input value={d.address} onChange={(e) => setD({ ...d, address: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={d.is_active} onChange={(e) => setD({ ...d, is_active: e.target.checked })} />Active</label>
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setD(null)}>Cancel</Button><Button loading={busy} disabled={!d.name.trim()} onClick={save}>Save</Button></div></div>)}
      </Modal>
    </>
  );
}
