import { ButtonHTMLAttributes, createContext, forwardRef, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes, useCallback, useContext, useEffect, useState } from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/* ---------- buttons ---------- */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost"; loading?: boolean };
export function Button({ variant = "primary", loading, className, children, disabled, ...rest }: BtnProps) {
  const styles = {
    primary: "bg-brand-500 text-white hover:bg-brand-600",
    secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-700",
    ghost: "text-slate-600 hover:bg-slate-100",
  }[variant];
  return (
    <button type="button" {...rest} disabled={disabled || loading}
      className={cx("inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed", styles, className)}>
      {loading && <Spinner small />}
      {children}
    </button>
  );
}

/* ---------- form controls ---------- */
const control = "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:bg-slate-100";
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => <input ref={ref} className={cx(control, className)} {...p} />);
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => <textarea ref={ref} rows={3} className={cx(control, className)} {...p} />);
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...p }, ref) => <select ref={ref} className={cx(control, className)} {...p}>{children}</select>);
Input.displayName = "Input"; Textarea.displayName = "Textarea"; Select.displayName = "Select";

export function Field({ label, error, hint, required, children }: { label: string; error?: string; hint?: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}{required && <span className="text-red-600"> *</span>}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
      {error && <span role="alert" className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

/* ---------- display ---------- */
export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-lg border border-slate-200 bg-white shadow-sm", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          <div className="flex gap-2">{actions}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-xl font-semibold">{title}</h1>{subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}</div>
      <div className="flex flex-wrap gap-2">{actions}</div>
    </div>
  );
}

const badgeColors: Record<string, string> = {
  Active: "bg-green-100 text-green-800", Completed: "bg-green-100 text-green-800",
  Pending: "bg-amber-100 text-amber-800", Inactive: "bg-slate-200 text-slate-700", Cancelled: "bg-slate-200 text-slate-700",
  Suspended: "bg-red-100 text-red-800", Overdue: "bg-red-100 text-red-800",
};
export const Badge = ({ children }: { children: string }) => (
  <span className={cx("inline-block rounded-full px-2 py-0.5 text-xs font-medium", badgeColors[children] ?? "bg-blue-100 text-blue-800")}>{children}</span>
);

export function Spinner({ small }: { small?: boolean }) {
  return <span role="status" aria-label="Loading" className={cx("inline-block animate-spin rounded-full border-2 border-slate-300 border-t-brand-500", small ? "h-4 w-4" : "h-6 w-6")} />;
}
export const Loading = () => <div className="flex justify-center py-10"><Spinner /></div>;

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <span>{message}</span>{onRetry && <Button variant="secondary" onClick={onRetry}>Retry</Button>}
    </div>
  );
}
export const EmptyState = ({ message, action }: { message: string; action?: ReactNode }) => (
  <div className="rounded-md border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500"><p>{message}</p>{action && <div className="mt-3">{action}</div>}</div>
);

/* ---------- table with loading / error / empty handling ---------- */
export interface Column<T> { header: string; cell: (row: T) => ReactNode; className?: string }
export function DataTable<T>({ columns, rows, loading, error, onRetry, empty, rowKey, onRowClick }: {
  columns: Column<T>[]; rows: T[] | undefined; loading?: boolean; error?: string | null; onRetry?: () => void;
  empty?: string; rowKey: (r: T) => string | number; onRowClick?: (r: T) => void;
}) {
  if (error) return <ErrorBox message={error} onRetry={onRetry} />;
  if (loading && !rows) return <Loading />;
  if (!rows || rows.length === 0) return <EmptyState message={empty ?? "Nothing to show."} />;
  return (
    <div className={cx("overflow-x-auto rounded-lg border border-slate-200 bg-white", loading && "opacity-60")}>
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50"><tr>{columns.map((c) => <th key={c.header} className={cx("px-3 py-2 text-left font-medium text-slate-600", c.className)}>{c.header}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={rowKey(r)} onClick={onRowClick ? () => onRowClick(r) : undefined} className={cx(onRowClick && "cursor-pointer hover:bg-slate-50")}>
              {columns.map((c) => <td key={c.header} className={cx("px-3 py-2 align-top", c.className)}>{c.cell(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
      <span>{total} results · page {page} of {pages}</span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

/* ---------- modal ---------- */
export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-5 shadow-xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">{title}</h2><Button variant="ghost" onClick={onClose} aria-label="Close">✕</Button></div>
        {children}
      </div>
    </div>
  );
}

/* ---------- toasts ---------- */
type Toast = { id: number; kind: "success" | "error"; text: string };
const ToastCtx = createContext<(text: string, kind?: Toast["kind"]) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const notify = useCallback((text: string, kind: Toast["kind"] = "success") => {
    const id = Date.now() + Math.random();
    setItems((t) => [...t, { id, kind, text }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={notify}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 z-50 space-y-2">
        {items.map((t) => <div key={t.id} className={cx("rounded-md px-4 py-2 text-sm text-white shadow-lg", t.kind === "success" ? "bg-green-600" : "bg-red-600")}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

export const StatCard = ({ label, value, tone }: { label: string; value: ReactNode; tone?: "warn" | "danger" }) => (
  <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
    <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
    <div className={cx("mt-1 text-2xl font-semibold", tone === "warn" && "text-amber-600", tone === "danger" && "text-red-600")}>{value}</div>
  </div>
);
