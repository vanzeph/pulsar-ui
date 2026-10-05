// Monthly returns heatmap: rows = compared runs, columns = months.

import type { EChartsCoreOption } from "../../lib/echartsSetup";
import { EChart } from "../../components/EChart";
import { fmtPct } from "../../format";
import { AXIS_STYLE, COLORS, RUN_PALETTE, tooltipStyle } from "../../theme";
import { monthlyReturns, type SeriesPoint } from "../../lib/metrics";

export interface MonthlySeries {
  runId: string;
  nav: SeriesPoint[];
}

export function MonthlyHeatmap({ series }: { series: MonthlySeries[] }) {
  const perRun = series.map((item) => ({
    runId: item.runId,
    returns: monthlyReturns(item.nav),
  }));
  const months = [...new Set(perRun.flatMap((item) => item.returns.map((r) => r.month)))]
    .sort();
  const data: Array<[number, number, number]> = [];
  perRun.forEach((item, row) => {
    const byMonth = new Map(item.returns.map((r) => [r.month, r.ret]));
    months.forEach((month, col) => {
      const ret = byMonth.get(month);
      if (ret !== undefined) data.push([col, row, ret]);
    });
  });
  const option: EChartsCoreOption = {
    backgroundColor: "transparent",
    animation: false,
    tooltip: tooltipStyle({
      position: "top",
      formatter: (params: { data: [number, number, number] }) => {
        const [col, row, ret] = params.data;
        return `${perRun[row].runId}<br/>${months[col]}：${fmtPct(ret)}`;
      },
    }),
    grid: { left: 130, right: 60, top: 10, bottom: 46 },
    xAxis: {
      type: "category",
      data: months,
      splitArea: { show: true },
      ...AXIS_STYLE,
    },
    yAxis: {
      type: "category",
      data: perRun.map((item) => item.runId),
      ...AXIS_STYLE,
      axisLabel: {
        color: COLORS.text,
        fontSize: 11,
        formatter: (id: string) => (id.length > 14 ? `${id.slice(0, 13)}…` : id),
      },
    },
    visualMap: {
      min: -0.05,
      max: 0.05,
      calculable: true,
      orient: "vertical",
      right: 0,
      top: "center",
      itemHeight: 120,
      textStyle: { color: COLORS.muted },
      formatter: (value: number) => fmtPct(value, 1),
      inRange: {
        // 红涨绿跌：正收益偏红，负收益偏绿
        color: [COLORS.down, "#1d2733", COLORS.up],
      },
    },
    series: [
      {
        type: "heatmap",
        data,
        label: {
          show: true,
          fontSize: 10,
          color: COLORS.text,
          formatter: (p: { data: [number, number, number] }) =>
            fmtPct(p.data[2], 1).replace("%", ""),
        },
        itemStyle: { borderColor: COLORS.bg, borderWidth: 2 },
      },
    ],
  };
  return (
    <div>
      <EChart option={option} height={Math.max(160, 70 + perRun.length * 46)} />
      <div className="chart-note">
        颜色按月收益着色（红涨绿跌）；空格表示该月无净值数据。色标范围固定 ±5%，
        <span style={{ color: RUN_PALETTE[0] }}>-</span>
        超出范围按端点色显示。
      </div>
    </div>
  );
}
