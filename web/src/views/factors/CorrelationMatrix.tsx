// Factor x factor correlation heatmap over aligned IC dates.

import type { EChartsCoreOption } from "../../lib/echartsSetup";
import { EChart } from "../../components/EChart";
import { fmtNum } from "../../format";
import { AXIS_STYLE, COLORS, tooltipStyle } from "../../theme";
import { pearson } from "../../lib/metrics";
import type { IcPoint } from "./normalize";

export function CorrelationMatrix({
  factors,
  series,
}: {
  factors: string[];
  series: Record<string, IcPoint[]>;
}) {
  const byDate = new Map<string, Map<string, number>>();
  for (const [factor, points] of Object.entries(series)) {
    for (const point of points) {
      let row = byDate.get(point.ts);
      if (!row) {
        row = new Map();
        byDate.set(point.ts, row);
      }
      row.set(factor, point.ic);
    }
  }
  const dates = [...byDate.values()].filter((row) => row.size === factors.length);
  const data: Array<[number, number, number | null]> = [];
  factors.forEach((fy, y) => {
    factors.forEach((fx, x) => {
      const xs: number[] = [];
      const ys: number[] = [];
      if (x !== y) {
        for (const row of dates) {
          const vx = row.get(fx);
          const vy = row.get(fy);
          if (vx !== undefined && vy !== undefined) {
            xs.push(vx);
            ys.push(vy);
          }
        }
      }
      const corr = x === y ? 1 : pearson(xs, ys);
      data.push([x, y, corr]);
    });
  });
  const option: EChartsCoreOption = {
    backgroundColor: "transparent",
    animation: false,
    tooltip: tooltipStyle({
      position: "top",
      formatter: (params: { data: [number, number, number | null] }) => {
        const [x, y, v] = params.data;
        return `${factors[y]} × ${factors[x]}<br/>相关系数：${v === null ? "样本不足" : fmtNum(v, 3)}<br/>共同样本：${x === y ? dates.length : "—"}`;
      },
    }),
    grid: { left: 110, right: 60, top: 10, bottom: 90 },
    xAxis: {
      type: "category",
      data: factors,
      ...AXIS_STYLE,
      axisLabel: { ...AXIS_STYLE.axisLabel, rotate: 30 },
    },
    yAxis: { type: "category", data: factors, ...AXIS_STYLE },
    visualMap: {
      min: -1,
      max: 1,
      calculable: true,
      orient: "vertical",
      right: 0,
      top: "center",
      itemHeight: 110,
      textStyle: { color: COLORS.muted },
      inRange: { color: [COLORS.accent, "#1d2733", COLORS.up] },
    },
    series: [
      {
        type: "heatmap",
        data,
        label: {
          show: true,
          fontSize: 10,
          color: COLORS.text,
          formatter: (p: { data: [number, number, number | null] }) =>
            p.data[2] === null ? "—" : fmtNum(p.data[2], 2),
        },
        itemStyle: { borderColor: COLORS.bg, borderWidth: 2 },
      },
    ],
  };
  return (
    <div>
      <EChart option={option} height={Math.max(240, 120 + factors.length * 46)} />
      <div className="chart-note">
        对齐各因子 IC 时序的共有日期后计算 Pearson 相关；共同样本不足时显示 —。
      </div>
    </div>
  );
}
