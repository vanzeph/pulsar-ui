// IC time series (bars) with a rolling-mean overlay and the scalar IR.

import type { EChartsCoreOption } from "../../lib/echartsSetup";
import { EChart } from "../../components/EChart";
import { datePart, fmtNum } from "../../format";
import { AXIS_STYLE, COLORS, tooltipStyle } from "../../theme";
import type { IcPoint } from "./normalize";

function rollingMean(values: number[], window: number): Array<number | null> {
  const out: Array<number | null> = [];
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
    if (i >= window) sum -= values[i - window];
    out.push(i >= window - 1 ? sum / window : null);
  }
  return out;
}

export function IcSeriesChart({
  factor,
  points,
  ir,
}: {
  factor: string;
  points: IcPoint[];
  ir: number | null;
}) {
  const values = points.map((p) => p.ic);
  const mean12 = rollingMean(values, 12);
  const option: EChartsCoreOption = {
    backgroundColor: "transparent",
    animation: false,
    legend: {
      top: 0,
      textStyle: { color: COLORS.text, fontSize: 11 },
      data: ["IC", "IC 12期均值"],
    },
    tooltip: tooltipStyle({ trigger: "axis", axisPointer: { type: "line" } }),
    grid: { left: 56, right: 16, top: 30, bottom: 46 },
    xAxis: {
      type: "category",
      data: points.map((p) => datePart(p.ts)),
      ...AXIS_STYLE,
    },
    yAxis: {
      type: "value",
      ...AXIS_STYLE,
      axisLabel: {
        ...AXIS_STYLE.axisLabel,
        formatter: (v: number) => v.toFixed(3),
      },
    },
    dataZoom: [
      { type: "inside" },
      { type: "slider", bottom: 2, height: 18 },
    ],
    series: [
      {
        name: "IC",
        type: "bar",
        data: values,
        itemStyle: { color: COLORS.accent, opacity: 0.75 },
      },
      {
        name: "IC 12期均值",
        type: "line",
        data: mean12,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.6, color: COLORS.up },
        itemStyle: { color: COLORS.up },
        connectNulls: false,
      },
    ],
  };
  return (
    <div className="chart-block">
      <div className="stat-row">
        <span className="stat">
          <span className="stat-label">IR</span>
          <span className="stat-value">{ir === null ? "—" : fmtNum(ir, 3)}</span>
        </span>
        <span className="stat">
          <span className="stat-label">样本期数</span>
          <span className="stat-value">{points.length}</span>
        </span>
        <span className="stat">
          <span className="stat-label">因子</span>
          <span className="stat-value">{factor}</span>
        </span>
      </div>
      <EChart option={option} height={300} />
    </div>
  );
}
