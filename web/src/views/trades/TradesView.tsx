// 交易分析：选 run → K 线叠加买卖点（lake bars + trades 关联）、
// 逐笔明细（含费用，服务端分页）、持仓周期（FIFO 配对）。

import { useEffect, useMemo, useState } from "react";
import { getAllFills, getLakeBars, getTrades, listRuns } from "../../api";
import type { BarsResponse, Fill, TradesResponse } from "../../types";
import { useAsync } from "../../hooks/useAsync";
import { Card } from "../../components/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { lakeSymbolCandidates } from "../../symbols";
import { KlineChart } from "./KlineChart";
import { FillsTable } from "./FillsTable";
import { HoldingPeriods } from "./HoldingPeriods";
import { roundTrips } from "./holding";

const PAGE_SIZE = 50;

interface BarsProbe {
  bars: BarsResponse | null;
  tried: string[];
  error: string | null;
}

async function probeBars(candidates: string[]): Promise<BarsProbe> {
  const tried: string[] = [];
  for (const symbol of candidates) {
    tried.push(symbol);
    try {
      const payload = await getLakeBars(symbol, { maxPoints: 2000 });
      if (payload.available && (payload.bars?.length ?? 0) > 0) {
        return { bars: payload, tried, error: null };
      }
      if (payload.available && (payload.total_bars ?? 0) === 0) {
        continue; // window empty: try next candidate prefix
      }
      return { bars: payload, tried, error: null }; // unavailable: surface reason
    } catch (cause) {
      return { bars: null, tried, error: cause instanceof Error ? cause.message : String(cause) };
    }
  }
  return { bars: null, tried, error: null };
}

export function TradesView() {
  const runsQuery = useAsync(() => listRuns(), []);
  const runs = runsQuery.data?.runs ?? [];
  const [runId, setRunId] = useState<string>("");
  const [symbol, setSymbol] = useState<string>("");

  useEffect(() => {
    if (runs.length > 0 && !runs.some((run) => run.run_id === runId)) {
      setRunId(runs[0].run_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runsQuery.data]);

  const allFillsQuery = useAsync(
    () => (runId ? getAllFills(runId) : Promise.resolve({ fills: [] as Fill[] })),
    [runId],
  );
  const fills: Fill[] = allFillsQuery.data?.fills ?? [];
  const symbols = useMemo(
    () => [...new Set(fills.map((fill) => fill.symbol))].sort(),
    [fills],
  );

  useEffect(() => {
    if (symbols.length > 0 && !symbols.includes(symbol)) {
      setSymbol(symbols[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbols]);

  const [page, setPage] = useState(1);
  const pageQuery = useAsync(
    () => (runId ? getTrades(runId, page, PAGE_SIZE) : Promise.resolve(null)),
    [runId, page],
  );
  useEffect(() => setPage(1), [runId]);

  const symbolFills = useMemo(
    () => fills.filter((fill) => fill.symbol === symbol),
    [fills, symbol],
  );
  const barsProbe = useAsync(
    () =>
      symbol ? probeBars(lakeSymbolCandidates(symbol)) : Promise.resolve({ bars: null, tried: [], error: null }),
    [symbol, fills.length],
  );

  if (runsQuery.loading) return <LoadingState label="加载 run 清单…" />;
  if (runsQuery.error) return <ErrorState message={runsQuery.error} />;

  const tradesPage: TradesResponse | null = pageQuery.data;
  const bars = barsProbe.data?.bars ?? null;

  return (
    <div className="view view-trades" data-view="trades">
      <Card
        title="策略行为审计"
        note={
          <span className="controls">
            <select data-role="run-select" value={runId} onChange={(e) => setRunId(e.target.value)}>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id}
                  {run.artifacts.events ? "" : "（无 events 工件）"}
                </option>
              ))}
            </select>
            <select data-role="symbol-select" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {symbols.length === 0 ? <option value="">（无成交）</option> : null}
              {symbols.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </span>
        }
      >
        {runs.length === 0 ? (
          <EmptyState title="没有发现任何 run" reason="配置的 runs 目录中无 run 工件目录。" />
        ) : allFillsQuery.loading ? (
          <LoadingState label="加载逐笔成交…" />
        ) : allFillsQuery.error ? (
          <ErrorState message={allFillsQuery.error} />
        ) : fills.length === 0 ? (
          <EmptyState
            title="该 run 无逐笔成交可分析"
            reason={
              allFillsQuery.data?.unavailableReason ??
              "events.parquet 中没有 fill 事件（或工件缺失）。"
            }
          />
        ) : (
          <div className="trade-summary stat-row">
            <span className="stat"><span className="stat-label">成交笔数</span><span className="stat-value">{fills.length}</span></span>
            <span className="stat"><span className="stat-label">交易代码</span><span className="stat-value">{symbols.join("、") || "—"}</span></span>
            <span className="stat">
              <span className="stat-label">费用合计</span>
              <span className="stat-value">
                {fills.reduce((sum, fill) => sum + (fill.fees_total ?? 0), 0).toFixed(2)}
              </span>
            </span>
            {bars?.symbol ? (
              <span className="stat"><span className="stat-label">行情代码</span><span className="stat-value">{bars.symbol}</span></span>
            ) : null}
          </div>
        )}
      </Card>

      <Card title="K 线与买卖点" note={bars ? `行情 ${bars.symbol}（${bars.returned_bars ?? 0} 根）` : undefined}>
        {!symbol || symbolFills.length === 0 ? (
          <EmptyState title="无买卖点可叠加" reason="该 run/代码下没有成交记录。" />
        ) : barsProbe.loading ? (
          <LoadingState label="加载行情…" />
        ) : barsProbe.error ? (
          <ErrorState message={barsProbe.error} />
        ) : !bars || !bars.available ? (
          <EmptyState
            title="数据湖中无该代码的行情"
            reason={bars?.reason ?? `在数据湖中未找到 ${symbol}（尝试了 ${(barsProbe.data?.tried ?? []).join("、") || "候选代码"}）。`}
            hint={<span>逐笔明细与持仓周期不受影响；K 线需要湖内 bars_1d 分区。</span>}
          />
        ) : (bars.bars?.length ?? 0) === 0 ? (
          <EmptyState title="该代码行情为空" reason="湖内有该 symbol 的分区但无行情行。" />
        ) : (
          <KlineChart bars={bars} fills={symbolFills} />
        )}
      </Card>

      <Card title="逐笔明细（含费用）" note="服务端分页">
        {pageQuery.loading && !tradesPage ? (
          <LoadingState />
        ) : pageQuery.error ? (
          <ErrorState message={pageQuery.error} />
        ) : !tradesPage || !tradesPage.available ? (
          <EmptyState title="逐笔明细不可用" reason={tradesPage?.reason ?? "该 run 无 events 工件。"} />
        ) : (
          <FillsTable
            fills={tradesPage.fills ?? []}
            page={tradesPage.page ?? page}
            pages={tradesPage.pages ?? 1}
            total={tradesPage.total_fills ?? 0}
            onPage={setPage}
            loading={pageQuery.loading}
          />
        )}
      </Card>

      <Card title="持仓周期" note="买入 → 卖出（FIFO 配对）">
        {fills.length === 0 ? (
          <EmptyState title="无持仓周期可分析" reason="需要带买卖对的成交记录。" />
        ) : (
          <HoldingPeriods trips={roundTrips(fills)} />
        )}
      </Card>
    </div>
  );
}
