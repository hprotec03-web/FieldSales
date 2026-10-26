import { useEffect, useState } from "react";
import { Button, Card, ErrorBox, Loading, PageHeader, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { api } from "../lib/api";
import { errorMessage } from "../lib/format";
import type { Permission, RoleFull } from "../lib/types";

export default function Roles() {
  const toast = useToast();
  const roles = useFetch(() => api.get<RoleFull[]>("/roles"), []);
  const perms = useFetch(() => api.get<Permission[]>("/permissions"), []);
  const [sel, setSel] = useState<Record<number, Set<string>>>({});
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    if (roles.data) setSel(Object.fromEntries(roles.data.map((r) => [r.id, new Set(r.permissions.map((p) => p.code))])));
  }, [roles.data]);

  if ((roles.loading && !roles.data) || (perms.loading && !perms.data)) return <Loading />;
  if (roles.error || perms.error || !roles.data || !perms.data) return <ErrorBox message={roles.error ?? perms.error ?? "Failed to load"} onRetry={() => { roles.reload(); perms.reload(); }} />;
  const groups = perms.data.reduce<Record<string, Permission[]>>((a, p) => { (a[p.code.split(".")[0]] ??= []).push(p); return a; }, {});

  const toggle = (rid: number, code: string) => {
    const next = new Set(sel[rid]); next.has(code) ? next.delete(code) : next.add(code); setSel({ ...sel, [rid]: next });
  };
  const save = async (r: RoleFull) => {
    setBusy(r.id);
    try { await api.put(`/roles/${r.id}/permissions`, { permission_codes: [...sel[r.id]] }); toast(`${r.name} permissions saved`); roles.reload(); } catch (e) { toast(errorMessage(e), "error"); } finally { setBusy(null); }
  };

  return (
    <>
      <PageHeader title="Roles & permissions" subtitle="Changes apply to every user with the role on their next request. The Administrator role is fixed." />
      <div className="space-y-4">
        {roles.data.map((r) => (
          <Card key={r.id} title={<>{r.name} <span className="ml-2 text-xs font-normal text-slate-500">{r.data_scope === "assigned" ? "sees only assigned customers" : "sees all company data"}</span></>}
            actions={r.name !== "Administrator" && <Button loading={busy === r.id} onClick={() => save(r)}>Save</Button>}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(groups).map(([g, list]) => (
                <fieldset key={g}><legend className="mb-1 text-xs font-semibold uppercase text-slate-500">{g}</legend>
                  {list.map((p) => (
                    <label key={p.id} className="flex items-center gap-2 py-0.5 text-sm">
                      <input type="checkbox" disabled={r.name === "Administrator"} checked={sel[r.id]?.has(p.code) ?? false} onChange={() => toggle(r.id, p.code)} />{p.code.split(".")[1]}
                    </label>
                  ))}
                </fieldset>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
