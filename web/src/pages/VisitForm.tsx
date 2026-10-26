import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Button, Card, ErrorBox, Field, Input, PageHeader, Select, Textarea, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { ApiError, api } from "../lib/api";
import { VISIT_OUTCOMES, errorMessage, localInputToIso, toLocalInput } from "../lib/format";
import type { Branch, Customer, Page, Visit } from "../lib/types";
import { CustomerFields, customerSchema, toPayload } from "./CustomerForm";

interface FormValues {
  purpose: string; notes: string; outcome: string; branch_id: string; visit_time: string;
  follow_up_date: string; follow_up_notes: string; new_customer: any;
}

export default function VisitForm() {
  const nav = useNavigate();
  const toast = useToast();
  const { can } = useAuth();
  const [sp] = useSearchParams();
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [customerId, setCustomerId] = useState<string>(sp.get("customer_id") ?? "");
  const [search, setSearch] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [geoMsg, setGeoMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, setError: setFieldError, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ defaultValues: { visit_time: toLocalInput(), outcome: "", branch_id: "", purpose: "", notes: "", follow_up_date: "", follow_up_notes: "" } });

  const results = useFetch(() => api.get<Page<Customer>>("/customers", { q: search, status: "Active", page_size: 20 }), [search]);
  const selected = useFetch(() => (customerId ? api.get<Customer>(`/customers/${customerId}`) : Promise.resolve(null)), [customerId]);
  const branches = useFetch(() => (can("Branch.View") ? api.get<Branch[]>("/branches") : Promise.resolve([])), []);
  useEffect(() => { if (!can("Customer.View")) setMode("new"); }, [can]);

  const captureLocation = () => {
    setGeoMsg(null);
    if (!navigator.geolocation) { setGeoMsg("Location is not supported on this device. You can still save the visit."); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => setCoords({ lat: Number(p.coords.latitude.toFixed(6)), lng: Number(p.coords.longitude.toFixed(6)) }),
      () => setGeoMsg("Location permission denied or unavailable. You can still save the visit without it."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const onSubmit = async (v: FormValues) => {
    setError(null);
    const body: Record<string, unknown> = {
      branch_id: v.branch_id ? Number(v.branch_id) : null, visit_time: localInputToIso(v.visit_time),
      purpose: v.purpose || null, notes: v.notes || null, outcome: v.outcome || null,
      latitude: coords?.lat ?? null, longitude: coords?.lng ?? null,
      follow_up_date: v.follow_up_date ? localInputToIso(v.follow_up_date) : null, follow_up_notes: v.follow_up_notes || null,
    };
    if (mode === "existing") {
      if (!customerId) { setError("Select a customer, or switch to “New customer”."); return; }
      body.customer_id = Number(customerId);
    } else {
      const parsed = customerSchema.safeParse(v.new_customer ?? {});
      if (!parsed.success) {
        parsed.error.issues.forEach((i) => setFieldError(`new_customer.${i.path[0]}` as any, { message: i.message }));
        return;
      }
      const nc = toPayload(parsed.data); delete nc.salesman_id;
      body.new_customer = nc;
    }
    try {
      const visit = await api.post<Visit>("/visits", body);
      if (photo) { try { await api.upload(`/visits/${visit.id}/photo`, photo); } catch (e) { toast(`Visit saved, but the photo failed: ${errorMessage(e)}`, "error"); } }
      toast(visit.follow_up_id ? "Visit and follow-up saved" : "Visit saved");
      nav(`/visits/${visit.id}`);
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.fieldErrors).length) setError(Object.entries(e.fieldErrors).map(([k, m]) => `${k}: ${m}`).join(" · "));
      else setError(errorMessage(e));
    }
  };

  return (
    <>
      <PageHeader title="Record visit" />
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {error && <ErrorBox message={error} />}
        <Card title="Customer">
          {can("Customer.View") && (
            <div className="mb-3 flex gap-2" role="tablist">
              <Button variant={mode === "existing" ? "primary" : "secondary"} onClick={() => setMode("existing")}>Existing customer</Button>
              <Button variant={mode === "new" ? "primary" : "secondary"} onClick={() => setMode("new")}>New customer</Button>
            </div>
          )}
          {mode === "existing" ? (
            <div className="space-y-2">
              {selected.data && <p className="rounded-md bg-brand-50 p-2 text-sm">Selected: <strong>{selected.data.name}</strong> · {selected.data.mobile} · {selected.data.city}</p>}
              <Input placeholder="Search customers by name, mobile or city…" aria-label="Search customers" value={search} onChange={(e) => setSearch(e.target.value)} />
              {results.error ? <ErrorBox message={results.error} onRetry={results.reload} /> : (
                <ul className="max-h-48 divide-y overflow-y-auto rounded-md border">
                  {results.loading && <li className="p-2 text-sm text-slate-500">Searching…</li>}
                  {!results.loading && !results.data?.items.length && <li className="p-2 text-sm text-slate-500">No customers found. Use “New customer” to add one during this visit.</li>}
                  {results.data?.items.map((c) => (
                    <li key={c.id}><button type="button" onClick={() => setCustomerId(String(c.id))} className={`w-full p-2 text-left text-sm hover:bg-slate-50 ${String(c.id) === customerId ? "bg-brand-50" : ""}`}>{c.name} <span className="text-slate-500">· {c.mobile} · {c.city}</span></button></li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-slate-600">The new customer will be created and assigned to you together with this visit.</p>
              <CustomerFields register={register} errors={errors} prefix="new_customer." />
            </div>
          )}
        </Card>

        <Card title="Visit details">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Visit time" required><Input type="datetime-local" {...register("visit_time", { required: true })} /></Field>
            <Field label="Outcome"><Select {...register("outcome")}><option value="">—</option>{VISIT_OUTCOMES.map((o) => <option key={o}>{o}</option>)}</Select></Field>
            <Field label="Purpose"><Input maxLength={300} {...register("purpose")} /></Field>
            {!!branches.data?.length && <Field label="Branch"><Select {...register("branch_id")}><option value="">No branch</option>{branches.data.filter((b) => b.is_active).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</Select></Field>}
            <div className="sm:col-span-2"><Field label="Notes"><Textarea {...register("notes")} /></Field></div>
            <div className="sm:col-span-2">
              <span className="mb-1 block text-sm font-medium text-slate-700">Location (optional)</span>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="secondary" onClick={captureLocation}>Capture my location</Button>
                {coords && <><span className="text-sm">{coords.lat}, {coords.lng}</span><Button variant="ghost" onClick={() => setCoords(null)}>Clear</Button></>}
              </div>
              {geoMsg && <p className="mt-1 text-xs text-amber-700">{geoMsg}</p>}
            </div>
            <div className="sm:col-span-2">
              <Field label="Photo (optional)" hint="JPEG, PNG or WebP, up to 5 MB.">
                <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </Field>
            </div>
          </div>
        </Card>

        {can("FollowUp.Create") && (
          <Card title="Schedule follow-up (optional)">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Follow-up date" hint="Leave empty to skip creating a follow-up."><Input type="datetime-local" {...register("follow_up_date")} /></Field>
              <Field label="Follow-up notes"><Input {...register("follow_up_notes")} /></Field>
            </div>
          </Card>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => nav(-1)}>Cancel</Button>
          <Button type="submit" loading={isSubmitting}>Save visit</Button>
        </div>
      </form>
    </>
  );
}
