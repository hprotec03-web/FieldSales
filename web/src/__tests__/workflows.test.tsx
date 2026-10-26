import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui";
import Login from "../pages/Login";
import FollowUpDetailPage from "../pages/FollowUpDetail";
import App from "../App";

const me = (permissions: string[], scope = "company") => ({
  id: 1, company_id: 1, branch_id: null, role_id: 1, username: "u", full_name: "Test User", email: null, mobile: null, status: "Active", created_at: "",
  role: { id: 1, name: "Role", data_scope: scope }, company_name: "Acme", permissions,
});
const json = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mockApi(routes: Record<string, (init?: RequestInit) => Response>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input).replace("/api/v1", "");
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    const h = routes[key];
    return Promise.resolve(h ? h(init) : json(404, { error: { code: "not_found", message: `unmocked ${key}` } }));
  });
}
const wrap = (ui: React.ReactNode, path = "/") => render(<MemoryRouter initialEntries={[path]}><ToastProvider><AuthProvider>{ui}</AuthProvider></ToastProvider></MemoryRouter>);

beforeEach(() => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => vi.restoreAllMocks());

describe("login", () => {
  it("shows validation errors and does not call the API when empty", async () => {
    const spy = mockApi({ "GET /auth/me": () => json(401, { error: { code: "unauthorized", message: "Not authenticated" } }) });
    wrap(<Routes><Route path="/login" element={<Login />} /></Routes>, "/login");
    await userEvent.click(await screen.findByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Username is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(spy.mock.calls.some(([u]) => String(u).includes("/auth/login"))).toBe(false);
  });

  it("shows the server error on bad credentials", async () => {
    mockApi({
      "GET /auth/me": () => json(401, { error: { code: "unauthorized", message: "Not authenticated" } }),
      "POST /auth/login": () => json(401, { error: { code: "unauthorized", message: "Invalid username or password" } }),
    });
    wrap(<Routes><Route path="/login" element={<Login />} /></Routes>, "/login");
    await userEvent.type(await screen.findByLabelText(/username/i), "bob");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Invalid username or password")).toBeInTheDocument();
  });
});

describe("permission-based navigation", () => {
  it("hides admin links from a salesman and shows them to an administrator", async () => {
    mockApi({ "GET /auth/me": () => json(200, me(["Customer.View", "Visit.View", "Visit.Create", "FollowUp.View"], "assigned")), "GET /dashboard": () => json(200, { kind: "salesman", assigned_customers: 0, created_by_me_visible: 0, total_visits: 0, todays_visits: 0, pending_followups: 0, overdue_followups: 0, upcoming_followups: [], recent_visits: [], recent_interactions: [] }) });
    const { unmount } = wrap(<App />);
    expect(await screen.findByRole("link", { name: "Customers" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Reports" })).not.toBeInTheDocument();
    unmount();
    vi.restoreAllMocks();
    mockApi({ "GET /auth/me": () => json(200, me(["Customer.View", "User.View", "Reports.View", "Company.Edit"])), "GET /dashboard": () => json(200, { kind: "admin", total_customers: 0, active_customers: 0, total_salesmen: 0, total_visits: 0, todays_visits: 0, pending_followups: 0, overdue_followups: 0, assignment_summary: { assigned_customers: 0, unassigned_customers: 0 }, upcoming_followups: [], recent_visits: [], salesman_summaries: [], recently_visited_customers: [] }) });
    wrap(<App />);
    expect(await screen.findByRole("link", { name: "Users" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reports" })).toBeInTheDocument();
  });
});

describe("follow-up outcome history", () => {
  const detail = (outcomes: any[]) => ({
    id: 5, customer_id: 2, user_id: 1, created_by_name: "Sara", visit_id: null, title: "Follow-up with Al Noor", notes: null, due_date: "2026-11-01T10:00:00Z",
    status: "Pending", completed_at: null, created_at: "2026-10-20T10:00:00Z", is_overdue: false,
    customer: { id: 2, name: "Al Noor", mobile: "+971500000001", city: "Dubai", status: "Active" }, assigned_salesman: { id: 1, full_name: "Sara" }, outcomes,
  });

  it("lists previous outcomes in order and appends a new one without removing history", async () => {
    let outcomes = [
      { id: 1, follow_up_id: 5, outcome_text: "Customer requested product details", recorded_by_user_id: 1, recorded_by_name: "Sara", recorded_at: "2026-10-25T08:00:00Z" },
      { id: 2, follow_up_id: 5, outcome_text: "Product details sent", recorded_by_user_id: 1, recorded_by_name: "Sara", recorded_at: "2026-10-27T08:00:00Z" },
    ];
    const spy = mockApi({
      "GET /auth/me": () => json(200, me(["FollowUp.View", "FollowUp.Edit", "FollowUp.Complete"], "assigned")),
      "GET /followups/5": () => json(200, detail(outcomes)),
      "POST /followups/5/outcomes": (init) => {
        const text = JSON.parse(String(init!.body)).outcome_text;
        outcomes = [...outcomes, { id: 3, follow_up_id: 5, outcome_text: text, recorded_by_user_id: 1, recorded_by_name: "Sara", recorded_at: "2026-10-29T08:00:00Z" }];
        return json(201, outcomes[2]);
      },
    });
    wrap(<Routes><Route path="/followups/:id" element={<FollowUpDetailPage />} /></Routes>, "/followups/5");
    expect(await screen.findByText("Customer requested product details")).toBeInTheDocument();
    expect(screen.getByText("Product details sent")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/what happened/i), "Customer requested a demonstration");
    await userEvent.click(screen.getByRole("button", { name: /add outcome/i }));

    expect(await screen.findByText("Customer requested a demonstration")).toBeInTheDocument();
    expect(screen.getByText("Customer requested product details")).toBeInTheDocument(); // earlier entries preserved
    const post = spy.mock.calls.find(([u, i]) => String(u).endsWith("/followups/5/outcomes") && i?.method === "POST");
    expect(post).toBeTruthy();
  });

  it("hides the add-outcome form for completed follow-ups", async () => {
    mockApi({
      "GET /auth/me": () => json(200, me(["FollowUp.View", "FollowUp.Edit"], "assigned")),
      "GET /followups/5": () => json(200, { ...detail([]), status: "Completed", completed_at: "2026-10-30T10:00:00Z" }),
    });
    wrap(<Routes><Route path="/followups/:id" element={<FollowUpDetailPage />} /></Routes>, "/followups/5");
    expect(await screen.findByText("No outcomes recorded yet.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("button", { name: /add outcome/i })).not.toBeInTheDocument());
  });
});
