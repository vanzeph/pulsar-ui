// 数据湖覆盖热图：symbol × year，按 ok 占比着色，tooltip 展示质量构成。

import type { EChartsCoreOption } from "../../lib/echartsSetup";
import { EChart } from "../../components/EChart";
import type { CoverageSymbol } from "../../types";
import { AXIS_STYLE, COLORS, tooltipStyle } from "../../theme";
import { fmtNum } from "../../format";

function okShare(year: { rows: number; quality: { ok: number } }): number {
  return year.rows > 0 ? year.quality.ok / year.rows : 0;
}

export function CoverageHeatmap({ symbols }: { symbols: CoverageSymbol[] }) {
  const years = [
    ...new Set(symbols.flatMap((entry) => entry.years.map((year) => year.year))),
  ].sort();
  const names = symbols.map((entry) => entry.symbol);
  const data: Array<[number, number, number]> = [];
  symbols.forEach((entry, row) => {
    const byYear = new Map(entry.years.map((year) => [year.year, year]));
    years.forEach((year, col) => {
      const block = byYear.get(year);
      if (block) data.push([col, row, okShare(block)]);
    });
  });
  const option: EChartsCoreOption = {
    backgroundColor: "transparent",
    animation: false,
    tooltip: tooltipStyle({
      position: "top",
      formatter: (params: { data: [number, number, number] }) => {
        const [col, row] = params.data;
        const block = symbols[row].years.find((year) => year.year === years[col]);
        if (!block) return "";
        const q = block.quality;
        return [
          `<b>${symbols[row].symbol} · ${block.year}</b>`,
          `行数 ${fmtNum(block.rows, 0)}`,
          `区间 ${block.first_ts.slice(0, 10)} ~ ${block.last_ts.slice(0, 10)}`,
          `质量：ok ${fmtNum(q.ok, 0)} · backfilled ${fmtNum(q.backfilled, 0)} · suspect ${fmtNum(q.suspect, 0)} · other ${fmtNum(q.other, 0)}`,
          `ok 占比 ${(okShare(block) * 100).toFixed(1)}%`,
        ].join("<br/>");
      },
    }),
    grid: { left: 110, right: 70, top: 10, bottom: 40 },
    xAxis: { type: "category", data: years.map(String), ...AXIS_STYLE },
    yAxis: {
      type: "category",
      data: names,
      ...AXIS_STYLE,
      axisLabel: { color: COLORS.text, fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: "vertical",
      right: 0,
      top: "center",
      itemHeight: 120,
      textStyle: { color: COLORS.muted },
      formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      inRange: { color: [COLORS.bad, COLORS.warn, COLORS.ok] },
    },
    series: [
      {
        type: "heatmap",
        data,
        label: {
          show: data.length <= 220,
          fontSize: 9,
          color: "#0e131a",
          formatter: (p: { data: [number, number, number] }) =>
            `${(p.data[2] * 100).toFixed(0)}`,
        },
        itemStyle: { borderColor: COLORS.bg, borderWidth: 2 },
      },
    ],
  };
  return (
    <div>
      <EChart option={option} height={Math.max(200, 90 + names.length * 40)} />
      <div className="chart-note">
        颜色 = 该 symbol×year 中 quality=ok 的行占比（红=低、黄=中、绿=全 ok）；
        缺失格子表示该年无分区。悬停查看 backfilled/suspect/other 明细。
      </div>
    </div>
  );
}
