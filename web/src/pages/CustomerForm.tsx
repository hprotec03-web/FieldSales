import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../auth/AuthContext";
import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader, Select, Textarea, useToast } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { ApiError, api } from "../lib/api";
import { BUSINESS_TYPES, errorMessage } from "../lib/format";
import type { Customer, Page, User } from "../lib/types";

export const customerSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  mobile: z.string().trim().regex(/^\+?[\d\s\-().]{6,20}$/, "Enter a valid phone number"),
  city: z.string().trim().min(1, "City is required").max(100),
  business_type: z.string().optional(),
  product: z.string().optional(),
  contact_person: z.string().max(200).optional(),
  contact_person_mobile: z.string().trim().regex(/^(\+?[\d\s\-().]{6,20})?$/, "Enter a valid phone number").optional(),
  address: z.string().max(500).optional(),
  country: z.string().max(100).optional(),
  email: z.string().trim().email("Enter a valid email").or(z.literal("")).optional(),
  location_url: z.string().trim().regex(/^(https?:\/\/.+)?$/i, "Must start with http:// or https://").optional(),
  notes: z.string().max(4000).optional(),
  salesman_id: z.string().optional(),
});
export type CustomerFormValues = z.infer<typeof customerSchema>;

/** Converts form strings to the API payload (empty -> null). */
export function toPayload(v: CustomerFormValues) {
  const o: Record<string, unknown> = {};
  Object.entries(v).forEach(([k, val]) => { o[k] = typeof val === "string" && val.trim() === "" ? null : val; });
  o.name = v.name; o.mobile = v.mobile; o.city = v.city;
  o.salesman_id = v.salesman_id ? Number(v.salesman_id) : null;
  return o;
}

export function CustomerFields({ register, errors, prefix = "" }: { register: any; errors: any; prefix?: string }) {
  const r = (n: string) => register(prefix + n);
  const e = (n: string) => (prefix ? errors?.[prefix.replace(".", "")]?.[n]?.message : errors?.[n]?.message);
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Name" required error={e("name")}><Input {...r("name")} /></Field>
      <Field label="Mobile" required error={e("mobile")}><Input inputMode="tel" {...r("mobile")} /></Field>
      <Field label="City" required error={e("city")}><Input {...r("city")} /></Field>
      <Field label="Country" error={e("country")}><Input placeholder="United Arab Emirates" {...r("country")} /></Field>
      <Field label="Business type" error={e("business_type")}><Select {...r("business_type")}><option value="">—</option>{BUSINESS_TYPES.map((b) => <option key={b}>{b}</option>)}</Select></Field>
      <Field label="Product" error={e("product")}><Select {...r("product")}><option value="">—</option>{BUSINESS_TYPES.map((b) => <option key={b}>{b}</option>)}</Select></Field>
      <Field label="Contact person" error={e("contact_person")}><Input {...r("contact_person")} /></Field>
      <Field label="Contact person mobile" error={e("contact_person_mobile")}><Input inputMode="tel" {...r("contact_person_mobile")} /></Field>
      <Field label="Email" error={e("email")}><Input type="email" {...r("email")} /></Field>
      <Field label="Location URL" error={e("location_url")}><Input placeholder="https://maps.google.com/…" {...r("location_url")} /></Field>
      <div className="sm:col-span-2"><Field label="Address" error={e("address")}><Input {...r("address")} /></Field></div>
      <div className="sm:col-span-2"><Field label="Notes" error={e("notes")}><Textarea {...r("notes")} /></Field></div>
    </div>
  );
}

export default function CustomerForm() {
  const { id } = useParams();
  const editing = !!id;
  const nav = useNavigate();
  const toast = useToast();
  const { can } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const existing = useFetch(() => (editing ? api.get<Customer>(`/customers/${id}`) : Promise.resolve(null)), [id]);
  const salesmen = useFetch(() => (!editing && can("Customer.Assign") ? api.get<Page<User>>("/users", { scope: "assigned", status: "Active", page_size: 200 }) : Promise.resolve(null)), []);
  const { register, handleSubmit, reset, setError: setFieldError, formState: { errors, isSubmitting } } = useForm<CustomerFormValues>({ resolver: zodResolver(customerSchema) });

  useEffect(() => {
    const c = existing.data;
    if (c) reset({ ...c, business_type: c.business_type ?? "", product: c.product ?? "", contact_person: c.contact_person ?? "", contact_person_mobile: c.contact_person_mobile ?? "",
      address: c.address ?? "", email: c.email ?? "", location_url: c.location_url ?? "", notes: c.notes ?? "", salesman_id: "" });
  }, [existing.data, reset]);

  const onSubmit = async (v: CustomerFormValues) => {
    setError(null);
    try {
      const payload = toPayload(v);
      if (editing) { delete payload.salesman_id; await api.put(`/customers/${id}`, payload); toast("Customer updated"); nav(`/customers/${id}`); }
      else { const c = await api.post<Customer>("/customers", payload); toast("Customer created"); nav(`/customers/${c.id}`); }
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.fieldErrors).length) Object.entries(e.fieldErrors).forEach(([k, m]) => setFieldError(k as any, { message: m }));
      else if (e instanceof ApiError && e.status === 409) setError(`${e.message}. Open the existing customer instead of creating a duplicate.`);
      else setError(errorMessage(e));
    }
  };

  if (editing && existing.loading) return <Loading />;
  if (editing && existing.error) return <ErrorBox message={existing.error} onRetry={existing.reload} />;
  return (
    <>
      <PageHeader title={editing ? "Edit customer" : "New customer"} />
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error && <ErrorBox message={error} />}
          <CustomerFields register={register} errors={errors} />
          {!editing && can("Customer.Assign") && (
            <Field label="Assign to salesman" hint="Optional - can be done later from the customer page.">
              <Select {...register("salesman_id")}><option value="">Unassigned</option>{salesmen.data?.items.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}</Select>
            </Field>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => nav(-1)}>Cancel</Button>
            <Button type="submit" loading={isSubmitting}>{editing ? "Save changes" : "Create customer"}</Button>
          </div>
        </form>
      </Card>
    </>
  );
}
