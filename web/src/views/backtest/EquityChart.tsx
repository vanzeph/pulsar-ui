// NAV overlay (top grid) + drawdown (bottom grid) with a shared dataZoom.

import type { EChartsCoreOption } from "../../lib/echartsSetup";
import { EChart } from "../../components/EChart";
import { datePart, fmtNum, fmtPct } from "../../format";
import { AXIS_STYLE, COLORS, RUN_PALETTE, tooltipStyle } from "../../theme";
import type { SeriesPoint } from "../../lib/metrics";
import { drawdownSeries } from "../../lib/metrics";

export interface EquitySeries {
  runId: string;
  nav: SeriesPoint[];
}

export function EquityChart({ series }: { series: EquitySeries[] }) {
  const option: EChartsCoreOption = {
    backgroundColor: "transparent",
    animation: false,
    legend: {
      top: 0,
      textStyle: { color: COLORS.text, fontSize: 11 },
      inactiveColor: COLORS.muted,
    },
    tooltip: tooltipStyle({
      trigger: "axis",
      axisPointer: { type: "line" },
      valueFormatter: (value: number) => fmtNum(value, 4),
    }),
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 56, right: 16, top: 30, height: 190 },
      { left: 56, right: 16, top: 252, height: 90 },
    ],
    xAxis: [
      {
        type: "category",
        gridIndex: 0,
        data: series[0]?.nav.map((p) => datePart(p.ts)) ?? [],
        boundaryGap: false,
        ...AXIS_STYLE,
        axisLabel: { ...AXIS_STYLE.axisLabel, show: false },
      },
      {
        type: "category",
        gridIndex: 1,
        data: series[0]?.nav.map((p) => datePart(p.ts)) ?? [],
        boundaryGap: false,
        ...AXIS_STYLE,
      },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        scale: true,
        ...AXIS_STYLE,
        axisLabel: {
          ...AXIS_STYLE.axisLabel,
          formatter: (v: number) => v.toFixed(3),
        },
      },
      {
        type: "value",
        gridIndex: 1,
        max: 0,
        ...AXIS_STYLE,
        axisLabel: {
          ...AXIS_STYLE.axisLabel,
          formatter: (v: number) => `${(v * 100).toFixed(1)}%`,
        },
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1] },
      { type: "slider", xAxisIndex: [0, 1], bottom: 2, height: 18 },
    ],
    series: series.map((item, index) => {
      const color = RUN_PALETTE[index % RUN_PALETTE.length];
      return [
        {
          name: item.runId,
          type: "line",
          xAxisIndex: 0,
          yAxisIndex: 0,
          showSymbol: false,
          data: item.nav.map((p) => p.value),
          lineStyle: { width: 1.6, color },
          itemStyle: { color },
          emphasis: { focus: "series" },
        },
        {
          name: `${item.runId} 回撤`,
          type: "line",
          xAxisIndex: 1,
          yAxisIndex: 1,
          showSymbol: false,
          data: drawdownSeries(item.nav).map((p) => p.value),
          lineStyle: { width: 1, color, opacity: 0.9 },
          areaStyle: { color, opacity: 0.18 },
          itemStyle: { color },
          tooltip: { valueFormatter: (v: number) => fmtPct(v) },
        },
      ];
    }).flat(),
  };
  return <EChart option={option} height={380} />;
}
