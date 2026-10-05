// Thin fetch layer over the read-only API. All requests are same-origin
// GETs against this service; the frontend never talks to anything else.

import type {
  BarsResponse,
  CoverageResponse,
  EquityResponse,
  FactorIcResponse,
  ManifestResponse,
  RunsResponse,
  TradesResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { method: "GET" });
  } catch (cause) {
    throw new ApiError(0, `无法连接本机服务（${path}）：${String(cause)}`);
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown; message?: string };
      if (body && typeof body === "object") {
        const d = body.detail ?? body.message;
        if (typeof d === "string") detail = d;
        else if (d && typeof d === "object") detail = JSON.stringify(d);
      }
    } catch {
      /* non-JSON error body: keep the status line */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function listRuns(): Promise<RunsResponse> {
  return get<RunsResponse>("/api/runs");
}

export function getEquity(runId: string, maxPoints = 2000): Promise<EquityResponse> {
  return get<EquityResponse>(
    `/api/runs/${encodeURIComponent(runId)}/equity?max_points=${maxPoints}`,
  );
}

export function getTrades(
  runId: string,
  page: number,
  pageSize: number,
): Promise<TradesResponse> {
  return get<TradesResponse>(
    `/api/runs/${encodeURIComponent(runId)}/trades?page=${page}&page_size=${pageSize}`,
  );
}

/** Fetch every fill of a run (bounded) by walking the server-side pages. */
export async function getAllFills(
  runId: string,
  maxPages = 40,
  pageSize = 500,
): Promise<{ fills: TradesResponse["fills"]; unavailableReason?: string; pages?: number }> {
  const first = await getTrades(runId, 1, pageSize);
  if (!first.available) return { fills: [], unavailableReason: first.reason };
  const fills = [...(first.fills ?? [])];
  const pages = first.pages ?? 1;
  for (let page = 2; page <= Math.min(pages, maxPages); page += 1) {
    const next = await getTrades(runId, page, pageSize);
    fills.push(...(next.fills ?? []));
  }
  return { fills, pages };
}

export function getManifest(runId: string): Promise<ManifestResponse> {
  return get<ManifestResponse>(`/api/runs/${encodeURIComponent(runId)}/manifest`);
}

export function getFactorIc(name: string): Promise<FactorIcResponse> {
  return get<FactorIcResponse>(`/api/factors/${encodeURIComponent(name)}/ic`);
}

export function getLakeCoverage(): Promise<CoverageResponse> {
  return get<CoverageResponse>("/api/lake/coverage");
}

export function getLakeBars(
  symbol: string,
  opts: { start?: string; end?: string; maxPoints?: number } = {},
): Promise<BarsResponse> {
  const params = new URLSearchParams();
  if (opts.start) params.set("start", opts.start);
  if (opts.end) params.set("end", opts.end);
  params.set("max_points", String(opts.maxPoints ?? 2000));
  const query = params.toString();
  return get<BarsResponse>(`/api/lake/bars/${encodeURIComponent(symbol)}?${query}`);
}
