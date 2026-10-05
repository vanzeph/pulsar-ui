// Pure client-side derivations over server-preaggregated series:
// drawdown, monthly returns, IC-series statistics, manifest flattening.

import type { EquityPoint } from "../types";
import { monthKey } from "../format";

export interface SeriesPoint {
  ts: string;
  value: number;
}

export function navSeries(points: EquityPoint[]): SeriesPoint[] {
  return points.map((p) => ({ ts: p.ts, value: p.nav }));
}

/** Drawdown series: nav / running-max - 1 (values in (-1, 0]). */
export function drawdownSeries(series: SeriesPoint[]): SeriesPoint[] {
  let peak = -Infinity;
  return series.map((point) => {
    peak = Math.max(peak, point.value);
    return { ts: point.ts, value: peak > 0 ? point.value / peak - 1 : 0 };
  });
}

export interface MonthlyReturn {
  month: string; // "YYYY-MM"
  ret: number; // fraction of 1
}

/** Month-over-month returns from the last NAV of each month. The curve's
 * first point (the session start, NAV 1.0) anchors the first month. */
export function monthlyReturns(series: SeriesPoint[]): MonthlyReturn[] {
  if (series.length === 0) return [];
  const lastByMonth = new Map<string, number>();
  for (const point of series) {
    lastByMonth.set(monthKey(point.ts), point.value);
  }
  const months = [...lastByMonth.keys()].sort();
  const out: MonthlyReturn[] = [];
  let prev = series[0].value;
  for (const month of months) {
    const nav = lastByMonth.get(month)!;
    if (prev > 0) out.push({ month, ret: nav / prev - 1 });
    prev = nav;
  }
  return out;
}

export function pearson(xs: number[], ys: number[]): number | null {
  const n = Math.min(xs.length, ys.length);
  if (n < 2) return null;
  let sx = 0;
  let sy = 0;
  for (let i = 0; i < n; i += 1) {
    sx += xs[i];
    sy += ys[i];
  }
  const mx = sx / n;
  const my = sy / n;
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < n; i += 1) {
    const a = xs[i] - mx;
    const b = ys[i] - my;
    num += a * b;
    dx += a * a;
    dy += b * b;
  }
  const den = Math.sqrt(dx * dy);
  return den > 0 ? num / den : null;
}

/** Flatten a JSON document into dotted-path leaves (arrays as JSON text). */
export function flattenJson(
  value: unknown,
  prefix = "",
  out: Map<string, string> = new Map(),
): Map<string, string> {
  if (value === null || value === undefined) {
    out.set(prefix || "(root)", "null");
  } else if (Array.isArray(value)) {
    out.set(prefix || "(root)", JSON.stringify(value));
  } else if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      out.set(prefix || "(root)", "{}");
    } else {
      for (const [key, child] of entries) {
        flattenJson(child, prefix ? `${prefix}.${key}` : key, out);
      }
    }
  } else {
    out.set(prefix || "(root)", JSON.stringify(value));
  }
  return out;
}

export interface ManifestRow {
  path: string;
  values: string[]; // per compared run; "" when the path is absent
  changed: boolean;
}

/** Diff several flattened documents against the first one (the base). */
export function diffManifests(flattened: Map<string, string>[]): ManifestRow[] {
  if (flattened.length === 0) return [];
  const paths = new Set<string>();
  for (const map of flattened) {
    for (const path of map.keys()) paths.add(path);
  }
  const rows: ManifestRow[] = [];
  for (const path of [...paths].sort()) {
    const values = flattened.map((map) => map.get(path) ?? "");
    const base = values[0];
    const changed = values.some((value) => value !== base);
    rows.push({ path, values, changed });
  }
  return rows;
}
