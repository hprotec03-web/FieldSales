import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";
import { fmtDateTime, localInputToIso, toLocalInput } from "../lib/format";

const jsonResponse = (status: number, body: unknown) =>
  Promise.resolve(new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

afterEach(() => { vi.restoreAllMocks(); document.cookie = "fs_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT"; });

describe("api client", () => {
  it("sends credentials and no CSRF header on GET", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(200, { ok: true }));
    await api.get("/customers", { q: "abc", empty: "" });
    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/customers?q=abc");
    expect(init.credentials).toBe("include");
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });

  it("adds the CSRF header from the cookie on unsafe methods", async () => {
    document.cookie = "fs_csrf=token123";
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(201, { id: 1 }));
    await api.post("/customers", { name: "x" });
    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("token123");
    expect(init.body).toBe(JSON.stringify({ name: "x" }));
  });

  it("maps the error envelope and exposes field errors", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(422, { error: { code: "validation_error", message: "Invalid request", details: [{ field: "mobile", message: "Enter a valid phone number" }] } }));
    const err = (await api.post("/customers", {}).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.fieldErrors).toEqual({ mobile: "Enter a valid phone number" });
  });

  it("returns undefined for 204 and reports network failures", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => Promise.resolve(new Response(null, { status: 204 })));
    await expect(api.post("/auth/logout")).resolves.toBeUndefined();
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => Promise.reject(new TypeError("fail")));
    await expect(api.get("/x")).rejects.toMatchObject({ code: "network_error" });
  });
});

describe("date helpers", () => {
  it("round-trips local datetime input through UTC ISO", () => {
    const local = toLocalInput(new Date(2026, 0, 15, 9, 30));
    expect(local).toBe("2026-01-15T09:30");
    expect(new Date(localInputToIso(local)).getTime()).toBe(new Date(2026, 0, 15, 9, 30).getTime());
  });
  it("formats missing values as a dash", () => { expect(fmtDateTime(null)).toBe("—"); });
});
