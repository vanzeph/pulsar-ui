// Quantile layered returns: mean return per factor quantile bucket.

import type { EChartsCoreOption } from "../../lib/echartsSetup";
import { EChart } from "../../components/EChart";
import { fmtPct } from "../../format";
import { AXIS_STYLE, COLORS, tooltipStyle } from "../../theme";
import type { QuantilePoint } from "./normalize";

export function QuantileChart({ points }: { points: QuantilePoint[] }) {
  const option: EChartsCoreOption = {
    backgroundColor: "transparent",
    animation: false,
    tooltip: tooltipStyle({
      trigger: "axis",
      valueFormatter: (value: number) => fmtPct(value),
    }),
    grid: { left: 64, right: 16, top: 16, bottom: 40 },
    xAxis: {
      type: "category",
      data: points.map((p) => p.quantile),
      name: "分位组",
      nameTextStyle: { color: COLORS.muted },
      ...AXIS_STYLE,
    },
    yAxis: {
      type: "value",
      ...AXIS_STYLE,
      axisLabel: {
        ...AXIS_STYLE.axisLabel,
        formatter: (v: number) => `${(v * 100).toFixed(1)}%`,
      },
    },
    series: [
      {
        type: "bar",
        data: points.map((p) => p.ret),
        barMaxWidth: 42,
        itemStyle: { color: COLORS.accent, opacity: 0.85 },
        label: {
          show: true,
          position: "outside",
          color: COLORS.text,
          fontSize: 10,
          formatter: (p: { value: number }) => fmtPct(p.value, 1),
        },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: COLORS.muted, type: "dashed" },
          data: [{ yAxis: 0 }],
        },
      },
    ],
  };
  return <EChart option={option} height={260} />;
}
