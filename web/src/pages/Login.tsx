import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../auth/AuthContext";
import { Button, Card, ErrorBox, Field, Input } from "../components/ui";
import { errorMessage } from "../lib/format";

const schema = z.object({ username: z.string().trim().min(1, "Username is required"), password: z.string().min(1, "Password is required") });
type Form = z.infer<typeof schema>;

export default function Login() {
  const { me, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) });

  if (me) return <Navigate to={loc.state?.from ?? "/"} replace />;

  const onSubmit = async (v: Form) => {
    setError(null);
    try { await login(v.username, v.password); nav(loc.state?.from ?? "/", { replace: true }); }
    catch (e) { setError(errorMessage(e)); }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <h1 className="mb-6 text-center text-3xl font-bold text-brand-600">FieldSales</h1>
        <Card title="Sign in">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {error && <ErrorBox message={error} />}
            <Field label="Username" error={errors.username?.message}><Input autoComplete="username" autoFocus {...register("username")} /></Field>
            <Field label="Password" error={errors.password?.message}><Input type="password" autoComplete="current-password" {...register("password")} /></Field>
            <Button type="submit" loading={isSubmitting} className="w-full">Sign in</Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
