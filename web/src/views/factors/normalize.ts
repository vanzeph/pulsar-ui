// Normalize the factor-IC payload's series fields. The exact item shape
// is owned by the future C3 artifacts extension; these readers accept the
// natural key spellings and refuse (rather than guess) anything else —
// an unrecognized shape is an explicit state, never fabricated data.

export interface IcPoint {
  ts: string;
  ic: number;
}

export interface QuantilePoint {
  quantile: string;
  ret: number;
}

function firstNumber(item: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = item[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function firstString(item: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = item[key];
    if (typeof value === "string" && value !== "") return value;
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }
  return null;
}

export function normalizeIcSeries(items: Array<Record<string, unknown>>): {
  points: IcPoint[];
  recognized: boolean;
} {
  const points: IcPoint[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") return { points: [], recognized: false };
    const ts = firstString(item, ["ts", "date", "datetime", "time"]);
    const ic = firstNumber(item, ["ic", "normal_ic", "pearson_ic", "ic_normal"]);
    if (ts === null || ic === null) {
      return { points: [], recognized: false };
    }
    points.push({ ts, ic });
  }
  return { points, recognized: true };
}

export function normalizeQuantileReturns(items: Array<Record<string, unknown>>): {
  points: QuantilePoint[];
  recognized: boolean;
} {
  const points: QuantilePoint[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") return { points: [], recognized: false };
    const quantile = firstString(item, ["quantile", "q", "layer", "level", "bucket"]);
    const ret = firstNumber(item, ["return", "mean_return", "ret", "mean", "avg_return"]);
    if (quantile === null || ret === null) {
      return { points: [], recognized: false };
    }
    points.push({ quantile, ret });
  }
  return { points, recognized: true };
}
