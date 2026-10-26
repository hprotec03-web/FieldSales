import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../auth/AuthContext";
import { Button, Card, ErrorBox, Field, Input, PageHeader, useToast } from "../components/ui";
import { ApiError, api } from "../lib/api";
import { errorMessage } from "../lib/format";

const pwSchema = z.object({
  current_password: z.string().min(1, "Enter your current password"),
  new_password: z.string().min(8, "At least 8 characters").regex(/[A-Za-z]/, "Must contain a letter").regex(/\d/, "Must contain a digit"),
  confirm: z.string(),
}).refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Passwords do not match" });
type PwForm = z.infer<typeof pwSchema>;

export default function Profile() {
  const { me, refresh } = useAuth();
  const toast = useToast();
  const [p, setP] = useState({ full_name: me?.full_name ?? "", email: me?.email ?? "", mobile: me?.mobile ?? "" });
  const [pErr, setPErr] = useState<string | null>(null);
  const [pBusy, setPBusy] = useState(false);
  const pw = useForm<PwForm>({ resolver: zodResolver(pwSchema) });
  const [pwErr, setPwErr] = useState<string | null>(null);

  const saveProfile = async () => {
    setPBusy(true); setPErr(null);
    try { await api.put("/auth/me", { full_name: p.full_name, email: p.email || null, mobile: p.mobile || null }); await refresh(); toast("Profile updated"); }
    catch (e) { setPErr(e instanceof ApiError && Object.keys(e.fieldErrors).length ? Object.values(e.fieldErrors).join(" · ") : errorMessage(e)); } finally { setPBusy(false); }
  };
  const changePw = async (v: PwForm) => {
    setPwErr(null);
    try { await api.post("/auth/change-password", { current_password: v.current_password, new_password: v.new_password }); toast("Password changed"); pw.reset(); }
    catch (e) { setPwErr(errorMessage(e)); }
  };

  return (
    <>
      <PageHeader title="My profile" subtitle={`${me?.username} · ${me?.role.name} · ${me?.company_name}`} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Details"><div className="space-y-3">{pErr && <ErrorBox message={pErr} />}
          <Field label="Full name" required><Input value={p.full_name} onChange={(e) => setP({ ...p, full_name: e.target.value })} /></Field>
          <Field label="Email"><Input type="email" value={p.email} onChange={(e) => setP({ ...p, email: e.target.value })} /></Field>
          <Field label="Mobile"><Input value={p.mobile} onChange={(e) => setP({ ...p, mobile: e.target.value })} /></Field>
          <Button loading={pBusy} disabled={!p.full_name.trim()} onClick={saveProfile}>Save</Button></div></Card>
        <Card title="Change password">
          <form className="space-y-3" onSubmit={pw.handleSubmit(changePw)} noValidate>{pwErr && <ErrorBox message={pwErr} />}
            <Field label="Current password" error={pw.formState.errors.current_password?.message}><Input type="password" autoComplete="current-password" {...pw.register("current_password")} /></Field>
            <Field label="New password" error={pw.formState.errors.new_password?.message}><Input type="password" autoComplete="new-password" {...pw.register("new_password")} /></Field>
            <Field label="Confirm new password" error={pw.formState.errors.confirm?.message}><Input type="password" autoComplete="new-password" {...pw.register("confirm")} /></Field>
            <Button type="submit" loading={pw.formState.isSubmitting}>Change password</Button></form></Card>
      </div>
    </>
  );
}
