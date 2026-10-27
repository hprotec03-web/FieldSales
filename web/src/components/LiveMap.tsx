/* Leaflet map for attendance: everyone's last known position, or one salesman's route for the day.
   Labels come from the API, so they are inserted with textContent (never as HTML). */
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

export interface MapPerson {
  id: number; name: string; lat: number; lng: number; at: string; accuracy: number | null;
  state: "working" | "on_break" | "checked_out"; stale: boolean;
}
export interface MapRoutePoint { lat: number; lng: number; at: string; kind: string; label: string; accuracy: number | null }

const STATE_COLOR: Record<MapPerson["state"], string> = { working: "#0ca30c", on_break: "#fab219", checked_out: "#94a3b8" };
const EVENT_COLOR: Record<string, string> = { check_in: "#0ca30c", break_start: "#fab219", break_end: "#2a78d6", check_out: "#d03b3b" };
const SERIES = "#2a78d6";

const time = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
export const ago = (iso: string, now = Date.now()) => {
  const m = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : `${Math.floor(m / 60)}h ${m % 60}m ago`;
};

function el(tag: string, style: Partial<CSSStyleDeclaration>, text?: string) {
  const e = document.createElement(tag);
  Object.assign(e.style, style);
  if (text !== undefined) e.textContent = text;
  return e;
}

function tooltip(lines: string[]) {
  const box = el("div", {});
  lines.forEach((t, i) => box.appendChild(el("div", i === 0 ? { fontWeight: "600" } : { color: "#475569" }, t)));
  return box;
}

function personIcon(p: MapPerson, selected: boolean) {
  const initials = p.name.split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase();
  const ring = p.stale && p.state === "working" ? "#d03b3b" : STATE_COLOR[p.state];
  const bubble = el("div", {
    width: "34px", height: "34px", borderRadius: "9999px", background: selected ? "#0f172a" : "#ffffff",
    color: selected ? "#ffffff" : "#0f172a", border: `3px solid ${ring}`, display: "flex", alignItems: "center",
    justifyContent: "center", font: "600 12px Inter, system-ui, sans-serif", boxShadow: "0 2px 8px rgba(15,23,42,.25)",
  }, initials);
  return L.divIcon({ html: bubble, className: "", iconSize: [34, 34], iconAnchor: [17, 17] });
}

function eventIcon(kind: string) {
  const dot = el("div", {
    width: "16px", height: "16px", borderRadius: "9999px", background: EVENT_COLOR[kind] ?? SERIES,
    border: "3px solid #ffffff", boxShadow: "0 1px 4px rgba(15,23,42,.35)",
  });
  return L.divIcon({ html: dot, className: "", iconSize: [16, 16], iconAnchor: [8, 8] });
}

export function LiveMap({ people, route, selectedId, onSelect, focus, fitKey, height = 420 }: {
  people: MapPerson[]; route: MapRoutePoint[] | null; selectedId: number | null; onSelect?: (id: number) => void;
  focus?: { lat: number; lng: number } | null; fitKey: string; height?: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const fitted = useRef<string>("");

  useEffect(() => {
    if (!box.current) return;
    const m = L.map(box.current, { zoomControl: true, scrollWheelZoom: true }).setView([25.2, 55.3], 10);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => m.invalidateSize()) : null;
    ro?.observe(box.current);
    return () => { ro?.disconnect(); m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current, g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    const bounds: L.LatLngExpression[] = [];

    if (route) { // route mode (empty while it is loading: draw nothing)
      const line = route.map((p) => [p.lat, p.lng] as L.LatLngTuple);
      L.polyline(line, { color: SERIES, weight: 4, opacity: 0.85, lineJoin: "round" }).addTo(g);
      route.forEach((p, i) => {
        const isLast = i === route.length - 1;
        const mk = p.kind === "tracking" && !isLast
          ? L.circleMarker([p.lat, p.lng], { radius: 4, color: "#ffffff", weight: 2, fillColor: SERIES, fillOpacity: 1 })
          : L.marker([p.lat, p.lng], { icon: eventIcon(isLast && p.kind === "tracking" ? "break_end" : p.kind), zIndexOffset: 500 });
        mk.bindTooltip(tooltip([p.label, `${time(p.at)}${p.accuracy != null ? ` · ±${Math.round(p.accuracy)} m` : ""}`]), { direction: "top", offset: [0, -6] });
        mk.addTo(g);
        bounds.push([p.lat, p.lng]);
      });
    } else {
      people.forEach((p) => {
        const mk = L.marker([p.lat, p.lng], { icon: personIcon(p, p.id === selectedId), zIndexOffset: p.id === selectedId ? 1000 : 0 });
        const status = p.state === "working" ? "Working" : p.state === "on_break" ? "On break" : "Checked out";
        mk.bindTooltip(tooltip([p.name, `${status} · updated ${ago(p.at)}`, p.accuracy != null ? `Accuracy ±${Math.round(p.accuracy)} m` : ""]),
          { direction: "top", offset: [0, -16] });
        if (onSelect) mk.on("click", () => onSelect(p.id));
        mk.addTo(g);
        bounds.push([p.lat, p.lng]);
      });
    }

    // fit to the data only when what is shown changes (not on every auto-refresh)
    if (fitted.current !== fitKey && bounds.length) {
      fitted.current = fitKey;
      m.stop();
      if (bounds.length === 1) m.setView(bounds[0], 15, { animate: false });
      else m.fitBounds(L.latLngBounds(bounds), { padding: [36, 36], maxZoom: 16, animate: false });
    }
  }, [people, route, selectedId, onSelect, fitKey]);

  useEffect(() => {
    if (focus && map.current) map.current.setView([focus.lat, focus.lng], Math.max(map.current.getZoom(), 15), { animate: true });
  }, [focus]);

  return <div ref={box} className="relative z-0 w-full overflow-hidden rounded-xl border border-slate-200" style={{ height }} />;
}
