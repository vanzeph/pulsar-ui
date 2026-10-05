// K-line (candlestick from /api/lake/bars) overlaid with this run's
// buy/sell fills as triangle markers at their fill price and date.

import type { EChartsCoreOption } from "../../lib/echartsSetup";
import { EChart } from "../../components/EChart";
import type { BarsResponse, Fill } from "../../types";
import { COLORS, AXIS_STYLE, tooltipStyle } from "../../theme";
import { datePart, fmtNum } from "../../format";

export function KlineChart({
  bars,
  fills,
}: {
  bars: BarsResponse;
  fills: Fill[];
}) {
  const rows = bars.bars ?? [];
  const dates = rows.map((bar) => datePart(bar.ts));
  const dateSet = new Set(dates);
  const markers = fills
    .filter((fill) => fill.price !== null && dateSet.has(datePart(fill.ts)))
    .map((fill) => ({
      value: [datePart(fill.ts), fill.price as number],
      itemStyle: { color: fill.side === "buy" ? COLORS.up : COLORS.down },
      symbol: fill.side === "buy" ? "triangle" : "path://M0,0 L8,0 L4,6 Z",
      symbolSize: 11,
      name: fill.side === "buy" ? "买入" : "卖出",
      fill,
    }));
  const dropped = fills.length - markers.length;

  const option: EChartsCoreOption = {
    backgroundColor: "transparent",
    animation: false,
    tooltip: tooltipStyle({
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: unknown) => {
        const list = params as Array<{ seriesName: string; value: unknown; data?: unknown }>;
        const parts: string[] = [];
        for (const item of list) {
          if (item.seriesName === "K线") {
            const [open, close, low, high] = item.value as number[];
            parts.push(`开 ${fmtNum(open, 2)} 收 ${fmtNum(close, 2)}<br/>低 ${fmtNum(low, 2)} 高 ${fmtNum(high, 2)}`);
          } else if (item.seriesName === "买卖点" && item.data) {
            const marker = item.data as { fill: Fill };
            parts.push(
              `${marker.fill.side === "buy" ? "买入" : "卖出"} ${fmtNum(marker.fill.price, 2)} × ${marker.fill.quantity}`,
            );
          }
        }
        return parts.join("<br/>");
      },
    }),
    grid: { left: 60, right: 64, top: 16, bottom: 48 },
    xAxis: { type: "category", data: dates, ...AXIS_STYLE },
    yAxis: { type: "value", scale: true, ...AXIS_STYLE },
    dataZoom: [
      { type: "inside", xAxisIndex: 0 },
      { type: "slider", xAxisIndex: 0, bottom: 2, height: 18 },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: rows.map((bar) => [bar.open, bar.close, bar.low, bar.high]),
        // 红涨绿跌
        itemStyle: {
          color: COLORS.up,
          color0: COLORS.down,
          borderColor: COLORS.up,
          borderColor0: COLORS.down,
        },
      },
      {
        name: "买卖点",
        type: "scatter",
        data: markers,
        z: 5,
      },
    ],
  };
  return (
    <div>
      <EChart option={option} height={400} />
      {dropped > 0 ? (
        <div className="chart-note chart-warn">
          {dropped} 笔成交的日期不在该 symbol 的行情区间内（行情
          {dates.length > 0 ? ` ${dates[0]} ~ ${dates[dates.length - 1]}` : "为空"}），
          对应买卖点未绘制。
        </div>
      ) : (
        <div className="chart-note">
          红色三角=买入、绿色倒三角=卖出（位于成交价）；K 线来自数据湖 /api/lake/bars。
        </div>
      )}
    </div>
  );
}
