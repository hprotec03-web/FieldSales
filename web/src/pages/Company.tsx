import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { ApiError, api } from "../lib/api";
import { errorMessage } from "../lib/format";
import type { Company as CompanyT } from "../lib/types";

export default function Company() {
  const { can, me } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(() => api.get<CompanyT[]>("/companies"), []);
  const [f, setF] = useState({ name: "", phone: "", email: "", address: "" });
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null); const [fe, setFe] = useState<Record<string, string>>({});
  useEffect(() => { const c = data?.[0]; if (c) setF({ name: c.name, phone: c.phone ?? "", email: c.email ?? "", address: c.address ?? "" }); }, [data]);
  if (loading && !data) return <Loading />;
  if (error || !data?.[0]) return <ErrorBox message={error ?? "Company not found"} onRetry={reload} />;
  const editable = can("Company.Edit");
  const save = async () => {
    setBusy(true); setErr(null); setFe({});
    try { await api.put(`/companies/${me!.company_id}`, { name: f.name, phone: f.phone || null, email: f.email || null, address: f.address || null }); toast("Company saved"); reload(); }
    catch (e) { if (e instanceof ApiError && Object.keys(e.fieldErrors).length) setFe(e.fieldErrors); else setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHeader title="Company" subtitle="Each company's data is fully isolated from every other company." />
      <Card><div className="max-w-xl space-y-3">{err && <ErrorBox message={err} />}
        <Field label="Name" required><Input disabled={!editable} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Phone"><Input disabled={!editable} value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <Field label="Email" error={fe.email}><Input disabled={!editable} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Address"><Input disabled={!editable} value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field>
        {editable && <Button loading={busy} disabled={!f.name.trim()} onClick={save}>Save</Button>}</div></Card>
    </>
  );
}
