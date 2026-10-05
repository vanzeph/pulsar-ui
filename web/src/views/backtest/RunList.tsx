// Run list with experiment grouping and multi-select for comparison.

import type { RunSummary } from "../../types";
import { datePart } from "../../format";
import { RUN_PALETTE } from "../../theme";

export const MAX_COMPARE = 6;

export interface RunGroup {
  key: string;
  runs: RunSummary[];
}

export function groupByExperiment(runs: RunSummary[]): RunGroup[] {
  const groups = new Map<string, RunSummary[]>();
  for (const run of runs) {
    const key = run.experiment_id ?? "（无实验分组）";
    const bucket = groups.get(key);
    if (bucket) bucket.push(run);
    else groups.set(key, [run]);
  }
  return [...groups.entries()]
    .map(([key, items]) => ({ key, runs: items }))
    .sort((a, b) => b.runs.length - a.runs.length || a.key.localeCompare(b.key));
}

export function RunList({
  runs,
  selected,
  onToggle,
}: {
  runs: RunSummary[];
  selected: string[];
  onToggle: (runId: string) => void;
}) {
  if (runs.length === 0) {
    return (
      <div className="state state-empty" data-state="empty">
        <div className="state-glyph">○</div>
        <div className="state-title">没有发现任何 run</div>
        <div className="state-reason">
          配置的 runs 目录为空或不包含 run 工件目录
          （run_manifest.json / events.parquet / metrics_report.json）。
        </div>
      </div>
    );
  }
  const groups = groupByExperiment(runs);
  return (
    <div className="run-list" data-view="backtest-run-list">
      {groups.map((group) => (
        <div key={group.key} className="run-group">
          <div className="run-group-head">
            <span className="run-group-tag" title="experiment_id（参数扫描族）">
              {group.key}
            </span>
            <span className="run-group-count">{group.runs.length} runs</span>
          </div>
          {group.runs.map((run) => {
            const index = selected.indexOf(run.run_id);
            const checked = index >= 0;
            const disabled = !checked && selected.length >= MAX_COMPARE;
            return (
              <label
                key={run.run_id}
                className={`run-item${checked ? " is-checked" : ""}${disabled ? " is-disabled" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  onChange={() => onToggle(run.run_id)}
                />
                {checked ? (
                  <span
                    className="run-swatch"
                    style={{ background: RUN_PALETTE[index % RUN_PALETTE.length] }}
                  />
                ) : null}
                <span className="run-id" title={run.run_id}>{run.run_id}</span>
                <span className="run-meta">
                  {datePart(run.start)} ~ {datePart(run.end)}
                </span>
                <span
                  className="run-badges"
                  title="工件可用性：manifest / events / metrics"
                >
                  <em data-artifact="manifest" data-on={run.artifacts.manifest}>M</em>
                  <em data-artifact="events" data-on={run.artifacts.events}>E</em>
                  <em data-artifact="metrics" data-on={run.artifacts.metrics}>R</em>
                </span>
              </label>
            );
          })}
        </div>
      ))}
    </div>
  );
}
