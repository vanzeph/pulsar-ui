// Display formatting helpers (A-share convention: red = up, green = down).

/** DuckDB/ISO timestamps come as "2026-06-09T00:00:00+08:00" or
 * "2026-06-09 00:00:00+08:00"; the date part is what the views show. */
export function datePart(ts: string | null | undefined): string {
  if (!ts) return "—";
  return ts.slice(0, 10);
}

export function monthKey(ts: string): string {
  return ts.slice(0, 7);
}

export function fmtNum(
  value: number | string | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(num)) return String(value);
  return num.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Metric keys the runs report expresses as fractions of 1. */
const PERCENT_METRIC_KEYS = new Set([
  "annual_return",
  "total_return",
  "annual_volatility",
  "max_drawdown",
  "turnover_ratio",
]);

export function isPercentMetric(key: string): boolean {
  return PERCENT_METRIC_KEYS.has(key);
}

export function fmtMetric(key: string, value: number | string | null): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (!Number.isFinite(value)) return "—";
  if (isPercentMetric(key)) return fmtPct(value);
  return fmtNum(value, 2);
}

/** Human label for a metric key: "annual_return" -> "年化收益". */
const METRIC_LABELS: Record<string, string> = {
  annual_return: "年化收益",
  annual_volatility: "年化波动",
  buy_value: "买入金额",
  fills: "成交笔数",
  final_equity: "期末权益",
  final_nav: "期末净值",
  max_drawdown: "最大回撤",
  max_drawdown_peak_ts: "回撤峰值日",
  max_drawdown_trough_ts: "回撤谷底日",
  sell_value: "卖出金额",
  sharpe: "Sharpe",
  total_return: "累计收益",
  trading_days: "交易日数",
  turnover_annualized: "年化换手",
  turnover_ratio: "换手率",
  turnover_value: "成交额",
};

export function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key;
}

/** Number formatting that keeps chart axis/tooltip values readable. */
export function fmtAxis(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${(value / 1e8).toFixed(1)}亿`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}
