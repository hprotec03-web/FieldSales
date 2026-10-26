/** Server timestamps are UTC ISO strings ending in Z; display in the browser's locale/time zone. */
export const fmtDateTime = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
export const fmtDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—");
/** Value for <input type="datetime-local"> from an ISO string, in local time. */
export const toLocalInput = (d: Date = new Date()) => {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
/** datetime-local string (local time) -> UTC ISO string for the API. */
export const localInputToIso = (v: string) => new Date(v).toISOString();
export const BUSINESS_TYPES = ["EzeeStitch", "Accounts", "Medical", "Tours", "Saloon", "Restaurant", "RealState", "Gym", "Mobile POS", "Super Market", "Basic POS Trading", "Basic Sales Trading"];
export const VISIT_OUTCOMES = ["Interested", "Not Interested", "Needs Follow-up", "Demo Scheduled", "Deal Closed", "No Answer", "Other"];
export const errorMessage = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");
