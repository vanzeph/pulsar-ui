// Multi-run metrics comparison table: metric rows x run columns.

import type { RunSummary } from "../../types";
import { fmtMetric, metricLabel } from "../../format";
import { RUN_PALETTE } from "../../theme";

const META_ROWS: Array<{ key: string; label: string }> = [
  { key: "experiment_id", label: "实验分组" },
  { key: "mode", label: "运行模式" },
  { key: "seed", label: "随机种子" },
  { key: "code_version", label: "代码版本" },
  { key: "start", label: "开始" },
  { key: "end", label: "结束" },
  { key: "initial_cash", label: "初始资金" },
];

function metaValue(run: RunSummary, key: string): string {
  const value = (run as unknown as Record<string, unknown>)[key];
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function MetricsTable({
  runs,
  baseId,
}: {
  runs: RunSummary[];
  baseId: string | null;
}) {
  const metricKeys = new Set<string>();
  for (const run of runs) {
    for (const key of Object.keys(run.metrics ?? {})) metricKeys.add(key);
  }
  const ordered = [...metricKeys].sort();
  return (
    <div className="table-wrap" data-view="backtest-metrics">
      <table className="data-table">
        <thead>
          <tr>
            <th>指标</th>
            {runs.map((run) => (
              <th key={run.run_id}>
                <span
                  className="run-swatch"
                  style={{
                    background:
                      RUN_PALETTE[
                        Math.max(runs.findIndex((r) => r.run_id === baseId), 0) %
                          RUN_PALETTE.length
                      ],
                  }}
                />
                <span className="run-id" title={run.run_id}>{run.run_id}</span>
                {run.run_id === baseId ? <span className="tag">基准</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {META_ROWS.map((row) => (
            <tr key={row.key} className="row-meta">
              <th>{row.label}</th>
              {runs.map((run) => (
                <td key={run.run_id}>{metaValue(run, row.key)}</td>
              ))}
            </tr>
          ))}
          {ordered.map((key) => (
            <tr key={key}>
              <th>{metricLabel(key)}</th>
              {runs.map((run) => (
                <td key={run.run_id}>
                  {fmtMetric(key, (run.metrics ?? {})[key] ?? null)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
