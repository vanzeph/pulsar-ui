// Typed shapes of the pulsar_ui.server read-only API payloads.
// The server answers missing artifacts with structured empty states
// (available=false + reason) on HTTP 200; only unknown run ids are 404.

export interface RunSummary {
  run_id: string;
  directory: string;
  mode: string | null;
  seed: number | string | null;
  code_version: string | null;
  experiment_id: string | null;
  sweep: Record<string, unknown> | null;
  start: string | null;
  end: string | null;
  initial_cash: number | null;
  metrics: Record<string, number | string | null> | null;
  final_nav: number | null;
  artifacts: { manifest: boolean; events: boolean; metrics: boolean };
  schema_support: {
    manifest_supported: boolean;
    events_supported: boolean;
    metrics_supported: boolean;
    events_schema_versions: number[];
  };
}

export interface RunsResponse {
  count: number;
  runs: RunSummary[];
}

export interface EquityPoint {
  ts: string;
  nav: number;
  equity: number;
  cash: number;
  market_value: number;
  kind: string;
}

export interface EquityResponse {
  run_id: string;
  available: boolean;
  reason?: string;
  initial_cash?: number;
  total_points?: number;
  returned_points?: number;
  downsampled?: boolean;
  max_points?: number;
  points?: EquityPoint[];
}

export interface Fill {
  seq: number;
  ts: string;
  symbol: string;
  side: "buy" | "sell";
  price: number | null;
  quantity: number | null;
  commission: number | null;
  stamp_duty: number | null;
  transfer_fee: number | null;
  fees_total: number;
}

export interface TradesResponse {
  run_id: string;
  available: boolean;
  reason?: string;
  source?: string;
  total_fills?: number;
  page?: number;
  page_size?: number;
  pages?: number;
  fills?: Fill[];
}

/** /api/runs/{id}/manifest returns the RunManifest document as-is, or this
 * explicit unavailable state. */
export type ManifestResponse =
  | Record<string, unknown>
  | { run_id: string; available: false; reason: string };

export interface FactorIcResponse {
  factor: string;
  available: boolean;
  reason?: string;
  checked_sources?: string[];
  pending?: string;
  ic_series: Array<Record<string, unknown>>;
  ir: number | null;
  quantile_returns: Array<Record<string, unknown>>;
}

export interface QualityMix {
  ok: number;
  backfilled: number;
  suspect: number;
  other: number;
}

export interface CoverageYear {
  year: number;
  rows: number;
  first_ts: string;
  last_ts: string;
  quality: QualityMix;
}

export interface CoverageSymbol {
  symbol: string;
  years: CoverageYear[];
}

export interface WatermarkEntry {
  source: string;
  dataset: string;
  partition: string;
  rows: number;
  synced_through: string;
  updated_at: string;
}

export interface CoverageResponse {
  available: boolean;
  reason?: string;
  symbols: CoverageSymbol[];
  totals?: { rows: number; ok: number; backfilled: number; suspect: number; other: number; symbols: number };
  watermarks: { available: boolean; reason?: string; entries?: WatermarkEntry[] };
}

export interface LakeBar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number | null;
  adjust_factor: number | null;
  quality: string | null;
}

export interface BarsResponse {
  available: boolean;
  reason?: string;
  symbol?: string;
  total_bars?: number;
  returned_bars?: number;
  downsampled?: boolean;
  max_points?: number;
  bars: LakeBar[];
}
