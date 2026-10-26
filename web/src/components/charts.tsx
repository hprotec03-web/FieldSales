/* Lightweight SVG/HTML charts for the dashboard (no chart library needed).
   Colors follow one rule each: a single series uses SERIES; follow-up states use the fixed STATUS colors. */
import { ReactNode, useEffect, useRef, useState } from "react";

export const SERIES = "#2a78d6";
export const SERIES_TRACK = "#cde2fb";
export const STATUS = { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b", neutral: "#c3c2b7" } as const;
const GRID = "#e8e7e1";
const BASELINE = "#c3c2b7";
const MUTED = "#6b6a66";

export const compact = (n: number) => new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n);

/** Width of an element, kept up to date on resize. */
function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Clean axis maximum and step (e.g. 0 / 5 / 10 / 15). */
function niceScale(max: number, ticks = 4) {
  if (max <= 0) return { top: ticks, step: 1 };
  const raw = max / ticks;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw && (s >= 1 || mag < 1)) ?? 10 * mag;
  const s = Math.max(1, step);
  return { top: Math.ceil(max / s) * s, step: s };
}

/** Bar path with a 4px rounded data-end and a square baseline. */
function columnPath(x: number, y: number, w: number, h: number, r = 4) {
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

function Tooltip({ x, y, children }: { x: number; y: number; children: ReactNode }) {
  return (
    <div role="tooltip" className="pointer-events-none absolute z-10 whitespace-nowrap -translate-x-1/2 -translate-y-full rounded-lg bg-slate-900 px-3 py-2 text-xs text-white shadow-xl"
      style={{ left: x, top: y - 10 }}>
      {children}
    </div>
  );
}

/* ---------- column chart (single series over time) ---------- */
export interface ColumnDatum { key: string; label: string; long: string; value: number; highlight?: string }

export function ColumnChart({ data, height = 240, unit = "visits", unitOne = "visit" }: { data: ColumnDatum[]; height?: number; unit?: string; unitOne?: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const pad = { top: 22, right: 8, bottom: 28, left: 32 };
  const plotW = Math.max(0, width - pad.left - pad.right);
  const plotH = height - pad.top - pad.bottom;
  const max = Math.max(0, ...data.map((d) => d.value));
  const { top, step } = niceScale(max);
  const band = data.length ? plotW / data.length : 0;
  const barW = Math.min(24, band * 0.62);
  const y = (v: number) => pad.top + plotH - (v / top) * plotH;
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
  const labelEvery = band < 34 ? 2 : 1;
  const maxIdx = max > 0 ? data.findIndex((d) => d.value === max) : -1;
  const last = data.length - 1;

  return (
    <div className="relative">
    <div ref={ref} className="relative w-full min-w-0 overflow-hidden" style={{ height }}>
      {width > 0 && (
        <svg className="absolute inset-0" width={width} height={height} role="img" aria-label={`Column chart of ${unit} per day`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? BASELINE : GRID} strokeWidth={1} />
              <text x={pad.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill={MUTED} style={{ fontVariantNumeric: "tabular-nums" }}>{compact(t)}</text>
            </g>
          ))}
          {data.map((d, i) => {
            const cx = pad.left + band * i + band / 2;
            const h = Math.max(d.value > 0 ? 2 : 0, plotH - (y(d.value) - pad.top));
            const showValue = d.value > 0 && (i === maxIdx || i === last);
            return (
              <g key={d.key}>
                {h > 0 && (
                  <path d={columnPath(cx - barW / 2, pad.top + plotH - h, barW, h)} fill={SERIES}
                    opacity={hover === null || hover === i ? 1 : 0.45} style={{ transition: "opacity 120ms" }} />
                )}
                {showValue && hover === null && (
                  <text x={cx} y={pad.top + plotH - h - 6} textAnchor="middle" fontSize={11} fontWeight={600} fill="#1f2937">{d.value}</text>
                )}
                {(i % labelEvery === (last % labelEvery)) && (
                  <text x={cx} y={height - 8} textAnchor="middle" fontSize={11} fill={i === last ? "#1f2937" : MUTED} fontWeight={i === last ? 600 : 400}>{d.label}</text>
                )}
                {/* hit target: the whole band, bigger than the bar */}
                <rect x={pad.left + band * i} y={pad.top} width={band} height={plotH} fill="transparent" tabIndex={0}
                  aria-label={`${d.long}: ${d.value} ${unit}`}
                  onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}
                  onFocus={() => setHover(i)} onBlur={() => setHover(null)} className="outline-none" />
              </g>
            );
          })}
        </svg>
      )}
    </div>
      {hover !== null && data[hover] && (
        <Tooltip x={pad.left + band * hover + band / 2} y={y(data[hover].value)}>
          <div className="text-sm font-semibold">{data[hover].value} {data[hover].value === 1 ? unitOne : unit}</div>
          <div className="text-slate-300">{data[hover].long}</div>
        </Tooltip>
      )}
    </div>
  );
}

/* ---------- horizontal bars (one series, compare categories) ---------- */
export interface BarDatum { key: string | number; label: string; value: number; note?: ReactNode }

export function HBarChart({ data, unit, unitOne = unit }: { data: BarDatum[]; unit: string; unitOne?: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="space-y-3" aria-label={`Bar chart of ${unit}`}>
      {data.map((d) => (
        <li key={d.key} className="group">
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate font-medium text-slate-700" title={d.label}>{d.label}</span>
            <span className="shrink-0 text-slate-500"><span className="font-semibold text-slate-900">{d.value}</span> {d.value === 1 ? unitOne : unit}{d.note}</span>
          </div>
          <div className="h-2.5 w-full rounded-full bg-slate-100">
            <div className="h-full rounded-full transition-[width,opacity] duration-500 group-hover:opacity-80"
              style={{ width: `${(d.value / max) * 100}%`, minWidth: d.value ? 6 : 0, background: SERIES }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ---------- part-to-whole: one stacked bar + labelled legend ---------- */
export interface Segment { key: string; label: string; value: number; color: string; icon: ReactNode }

export function StackedBar({ segments }: { segments: Segment[] }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const [hover, setHover] = useState<string | null>(null);
  const pct = (v: number) => (total ? Math.round((v / total) * 100) : 0);
  return (
    <div>
      <div className="flex h-3.5 w-full gap-[2px] overflow-hidden rounded-full bg-slate-100" role="img"
        aria-label={segments.map((s) => `${s.label} ${s.value}`).join(", ")}>
        {total > 0 && segments.filter((s) => s.value > 0).map((s) => (
          <div key={s.key} className="h-full transition-opacity" title={`${s.label}: ${s.value} (${pct(s.value)}%)`}
            onPointerEnter={() => setHover(s.key)} onPointerLeave={() => setHover(null)}
            style={{ width: `${(s.value / total) * 100}%`, background: s.color, opacity: hover && hover !== s.key ? 0.4 : 1 }} />
        ))}
      </div>
      <ul className="mt-4 space-y-1">
        {segments.map((s) => (
          <li key={s.key} onPointerEnter={() => setHover(s.key)} onPointerLeave={() => setHover(null)}
            className={`flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm transition-colors ${hover === s.key ? "bg-slate-50" : ""}`}>
            <span className="flex h-6 w-6 items-center justify-center rounded-md" style={{ background: `${s.color}22`, color: s.color }}>{s.icon}</span>
            <span className="flex-1 text-slate-700">{s.label}</span>
            <span className="font-semibold text-slate-900">{s.value}</span>
            <span className="w-10 text-right text-xs text-slate-500" style={{ fontVariantNumeric: "tabular-nums" }}>{pct(s.value)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------- small pieces ---------- */
export function Sparkline({ values, width = 96, height = 32 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const max = Math.max(1, ...values);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * (width - 6) + 3, height - 4 - (v / max) * (height - 8)]);
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg width={width} height={height} aria-hidden="true">
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="#b9c3d0" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lx} cy={ly} r={4} fill={SERIES} stroke="#fff" strokeWidth={2} />
    </svg>
  );
}

export function Meter({ value, total }: { value: number; total: number }) {
  const p = total ? Math.min(100, (value / total) * 100) : 0;
  return (
    <div className="h-2.5 w-full rounded-full" style={{ background: SERIES_TRACK }} role="meter" aria-valuemin={0} aria-valuemax={total} aria-valuenow={value}>
      <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${p}%`, background: SERIES }} />
    </div>
  );
}

/** Chart / Table switch so every chart has a readable table twin. */
export function ViewToggle({ value, onChange }: { value: "chart" | "table"; onChange: (v: "chart" | "table") => void }) {
  return (
    <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium" role="group" aria-label="View">
      {(["chart", "table"] as const).map((v) => (
        <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}
          className={`rounded-md px-2.5 py-1 capitalize transition ${value === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>{v}</button>
      ))}
    </div>
  );
}

export function MiniTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="max-h-64 overflow-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 bg-slate-50"><tr>{head.map((h, i) => <th key={h} className={`px-3 py-2 font-medium text-slate-600 ${i ? "text-right" : "text-left"}`}>{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, ri) => <tr key={ri}>{r.map((c, i) => <td key={i} className={`px-3 py-1.5 ${i ? "text-right font-medium" : "text-slate-700"}`} style={i ? { fontVariantNumeric: "tabular-nums" } : undefined}>{c}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}
