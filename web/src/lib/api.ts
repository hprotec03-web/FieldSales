// Thin fetch wrapper: cookie auth (HttpOnly) + CSRF double-submit header, uniform error handling.
const BASE: string = (import.meta as any).env?.VITE_API_BASE ?? "";
const API = `${BASE}/api/v1`;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: any) {
    super(message);
  }
  /** field -> message map for 422 validation errors */
  get fieldErrors(): Record<string, string> {
    if (this.code !== "validation_error" || !Array.isArray(this.details)) return {};
    return Object.fromEntries(this.details.map((d: any) => [d.field, d.message]));
  }
}

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: (() => void) | null) => { onUnauthorized = fn; };

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)fs_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

function qs(params?: Record<string, unknown>): string {
  if (!params) return "";
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function toError(res: Response): Promise<ApiError> {
  let body: any = null;
  try { body = await res.json(); } catch { /* not json */ }
  const e = body?.error;
  return new ApiError(res.status, e?.code ?? "http_error", e?.message ?? `Request failed (${res.status})`, e?.details);
}

async function request<T>(method: string, path: string, opts: { body?: unknown; params?: Record<string, unknown>; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();
  let res: Response;
  try {
    res = await fetch(`${API}${path}${qs(opts.params)}`, { method, headers, body, credentials: "include" });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Check your connection and try again.");
  }
  if (res.status === 401 && !path.startsWith("/auth/login")) onUnauthorized?.();
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) => request<T>("GET", path, { params }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  del: <T>(path: string) => request<T>("DELETE", path),
  upload: <T>(path: string, file: File) => { const f = new FormData(); f.append("file", file); return request<T>("POST", path, { form: f }); },
  /** Downloads a CSV report (authenticated) and triggers a browser save. */
  async downloadCsv(path: string, params: Record<string, unknown>, filename: string) {
    const res = await fetch(`${API}${path}${qs({ ...params, format: "csv" })}`, { credentials: "include" });
    if (!res.ok) throw await toError(res);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  },
  /** Fetches a private image with credentials and returns an object URL. */
  async imageUrl(path: string): Promise<string> {
    const res = await fetch(`${BASE}${path}`, { credentials: "include" });
    if (!res.ok) throw await toError(res);
    return URL.createObjectURL(await res.blob());
  },
};
