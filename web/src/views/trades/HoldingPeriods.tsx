// 持仓周期视图：FIFO 配对的持有区间，时间轴上的横条 + 明细表。

import type { RoundTrip } from "./holding";
import { datePart, fmtNum } from "../../format";
import { COLORS } from "../../theme";

function toTime(ts: string): number {
  return new Date(ts.includes("T") ? ts : ts.replace(" ", "T")).getTime();
}

export function HoldingPeriods({ trips }: { trips: RoundTrip[] }) {
  if (trips.length === 0) {
    return (
      <div className="state state-empty" data-state="empty">
        <div className="state-glyph">○</div>
        <div className="state-title">无可展示的持仓周期</div>
        <div className="state-reason">
          该 run 没有可按 FIFO 配对的买卖对（需要至少一笔买入后随后的卖出）。
        </div>
      </div>
    );
  }
  const sorted = [...trips].sort((a, b) => toTime(a.openTs) - toTime(b.openTs));
  const min = toTime(sorted[0].openTs);
  const max = Math.max(...sorted.map((t) => toTime(t.closeTs)));
  const span = Math.max(max - min, 1);
  const pct = (ts: number) => ((ts - min) / span) * 100;

  return (
    <div className="holding" data-view="trades-holding">
      <div className="holding-axis">
        <div className="holding-ticks">
          <span>{datePart(new Date(min).toISOString())}</span>
          <span>{datePart(new Date(max).toISOString())}</span>
        </div>
        <div className="holding-rows">
          {sorted.slice(0, 60).map((trip, index) => {
            const left = pct(toTime(trip.openTs));
            const width = Math.max(pct(toTime(trip.closeTs)) - left, 0.6);
            const gain = (trip.pnl ?? 0) >= 0;
            return (
              <div
                key={`${trip.symbol}-${index}`}
                className="holding-row"
                title={`${trip.symbol} ${datePart(trip.openTs)} → ${datePart(trip.closeTs)} · ${trip.quantity} 股 · 盈亏 ${fmtNum(trip.pnl, 2)}`}
              >
                <span className="holding-label">{trip.symbol}</span>
                <span className="holding-track">
                  <span
                    className="holding-bar"
                    style={{
                      left: `${left}%`,
                      width: `${width}%`,
                      background: gain ? COLORS.up : COLORS.down,
                    }}
                  />
                </span>
              </div>
            );
          })}
        </div>
      </div>
      {sorted.length > 60 ? (
        <div className="chart-note">仅展示前 60 个持仓周期（共 {sorted.length} 个）。</div>
      ) : null}
      <table className="data-table holding-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>开仓日</th>
            <th>平仓日</th>
            <th>数量</th>
            <th>开仓价</th>
            <th>平仓价</th>
            <th>费用</th>
            <th>盈亏</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((trip, index) => (
            <tr key={`${trip.symbol}-row-${index}`}>
              <td>{trip.symbol}</td>
              <td>{datePart(trip.openTs)}</td>
              <td>{datePart(trip.closeTs)}</td>
              <td>{fmtNum(trip.quantity, 0)}</td>
              <td>{fmtNum(trip.openPrice, 4)}</td>
              <td>{fmtNum(trip.closePrice, 4)}</td>
              <td>{fmtNum(trip.fees, 2)}</td>
              <td className={(trip.pnl ?? 0) >= 0 ? "cell-up" : "cell-down"}>
                {fmtNum(trip.pnl, 2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
